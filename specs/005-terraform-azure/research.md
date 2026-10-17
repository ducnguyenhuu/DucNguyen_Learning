# Research: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

## R1 — Terraform State Backend Bootstrap

**Decision**: A separate `infrastructure/terraform/bootstrap/` Terraform config (or a Bash script using `az` CLI) creates the Azure Storage Account, container, and resource group for remote state. This runs once, manually, before the main `terraform init`.

**Rationale**: Terraform cannot manage its own state backend — the storage account must exist before `terraform init` configures the backend. This is the standard chicken-and-egg pattern. A small bootstrap script is simpler than a separate Terraform config for one resource group + one storage account.

**Alternatives considered**:
- *Terraform Cloud / HCP*: Adds a third-party dependency and cost. Azure Storage is simpler and Azure-native (ADR-001).
- *Local state*: Violates FR-002 (multi-operator collaboration) and is dangerous for shared infrastructure.
- *ARM template for bootstrap*: Works but introduces a second IaC language for no benefit.

## R2 — Container Apps Environment Networking

**Decision**: A VNet-integrated, **Consumption-only** Container Apps environment in a dedicated `/23` subnet (`sn-cae`), with external ingress. (Replaces the AKS CNI Overlay decision, per ADR-023, 2026-10-16.)

**Rationale**: VNet integration is what lets the app reach Azure SQL and Key Vault through their private endpoints and the existing private DNS zones. A Consumption-only environment needs a `/23` and no subnet delegation, and carries no fixed node cost, unlike a workload-profiles environment with a dedicated profile. External ingress is required because Developer-tier APIM is not VNet-integrated (R3).

**Alternatives considered**:
- *Workload profiles environment*: `/27` minimum and dedicated-profile pricing; no benefit for one small service in dev.
- *Internal-only environment*: Cleaner, but APIM Developer cannot reach it without Premium VNet integration (R3).
- *Environment outside the VNet*: Cannot use the SQL and Key Vault private endpoints, failing FR-006.

## R3 — APIM SKU and VNet Integration

**Decision**: APIM Developer tier, **not** VNet-integrated. APIM connects to the container app's **public ingress**, restricted by the app's ingress IP restrictions to the APIM instance's public IPs (clarified 2026-09-26, spec.md FR-007; the restriction mechanism moved from an AKS NSG to Container Apps ingress rules per ADR-023).

**Rationale**: APIM VNet integration (internal or external mode) requires the Premium tier (~$2,800/month) or the newer stv2 platform on Developer tier with significant provisioning time (45–60 min). For dev, the simpler approach is APIM Developer tier calling the container app's ingress directly, with the ingress IP allow-list as the compensating control so the "last hop" isn't wide open to the internet. Unlike the NSG it replaces, the allow-list takes the APIM instance's real IPs directly, because the APIM instance does not depend on the app; only the APIM *API definition* does. No two-phase apply is needed. The networking still proves the routing topology (Front Door → APIM → AKS) without the Premium cost.

**Alternatives considered**:
- *APIM Premium with full VNet integration*: Proves private networking but costs ~$2,800/month for dev — far exceeds the budget for the entire environment.
- *APIM Basic*: Cheaper but lacks developer portal and some policy features useful for learning.
- *Skip APIM*: Violates the roadmap's explicit inclusion and the target architecture in idea.md §17.
- *Public ingress IP, unrestricted*: Simplest, but leaves the ingress open to the entire internet, not just APIM — rejected during clarification in favor of the IP-restricted option.

**Correction (if needed)**: If Developer tier stv2 supports VNet injection at dev cost, prefer that. Verify during implementation.

## R4 — Managed Identity for ACR, SQL and Key Vault

**Decision**: Two **user-assigned managed identities** attached to the one container app: `id-tenancy-api` (ACR pull, Azure SQL) and `id-otel-collector` (Key Vault secret read). The licence key is a Container Apps **Key Vault secret reference** (`key_vault_secret_id` + identity), mounted into the collector sidecar as a **file** via a `Secret` volume. (Replaces AKS workload identity federation + Key Vault CSI, per ADR-023.)

**Rationale**: No federation, OIDC issuer or service-account wiring exists, and the two-phase apply the AKS design needed disappears. Mounting the secret as a file keeps the SC-004 property that the key is never an environment variable. Separate identities keep least privilege on the Azure side even though both run in one app.

**Alternatives considered**:
- *System-assigned identity*: One identity for everything; cannot separate ACR/SQL from Key Vault access and is recreated on every destroy.
- *Secret as an environment variable (`secretRef`)*: Simpler, but makes the licence key an environment variable in the process, which US3 forbids.
- *Direct Key Vault SDK calls*: Needs application code changes and does not help the Collector.

**Open risk**: The Key Vault has public access disabled. Whether the Container Apps platform resolves the secret reference through the private endpoint (and whether Terraform can write the secret from outside the VNet) is unverified until the first apply.

## R5 — Front Door + APIM Integration Pattern

**Decision**: Front Door Standard tier with APIM as the origin. Front Door handles TLS termination on `*.azurefd.net`, WAF (optional), and global load balancing. APIM handles API policies, rate limiting, and backend routing.

**Rationale**: This is the documented Microsoft pattern for the enterprise API gateway topology. Front Door provides edge TLS and caching; APIM provides API management. In dev, Front Door's global distribution is unnecessary but proves the wiring and the topology that production would use.

**Alternatives considered**:
- *Front Door directly to Container Apps*: Skips APIM, losing the API management layer the roadmap requires.
- *APIM as the sole edge*: No CDN/WAF/global distribution. Works for dev but doesn't prove the target topology.
- *Azure Application Gateway*: Regional only; Front Door is the prescribed component in idea.md §17.

## R6 — Azure SQL Authentication Mode

**Decision**: Azure AD-only authentication. SQL Server is provisioned with `azuread_authentication_only = true`. The Tenancy API's managed identity is granted `db_datareader` and `db_datawriter` roles. No SQL auth login exists.

**Rationale**: Constitution Principle V prohibits stored credentials. Azure AD-only auth eliminates the SA password entirely — there is no SQL auth fallback to accidentally expose. The managed identity used by the application authenticates via Azure AD token, with no connection string containing a password.

**Alternatives considered**:
- *Mixed mode (SQL + Azure AD)*: Allows fallback to SA password, which is a secret that must be managed and can leak.
- *Azure AD auth with SQL admin fallback*: Common but violates the "no stored credentials" principle for database access.

## R7 — Terraform-managed Container App vs Helm / Kubernetes manifests

**Decision**: The container app is an `azurerm_container_app` resource in the `containerapp` Terraform module. A deploy is a `terraform apply` that changes `api_image_tag`; there is no Helm chart or manifest set. (Replaces the Helm decision, per ADR-023.)

**Rationale**: One tool owns the revision, so there is no drift between Terraform and a second deploy tool. ADR-012's "Terraform provisions, Helm deploys" split disappears with Kubernetes. Revisions give release history, and recovery is redeploying a known-good tag.

**Alternatives considered**:
- *`az containerapp update` with `ignore_changes` on the image*: Avoids a full apply per deploy, but creates exactly the drift this decision avoids.
- *Bicep/ARM for the app only*: A second IaC language for no benefit.

**Consequence**: The first-ever apply is two-step, because the app cannot be created without an image already in ACR: `terraform apply -target=module.acr`, then `deploy.sh`. A precondition on the app fails the plan with a clear message if `api_image_tag` is empty.

## R8 — Replicas, Probes and Sizing

**Decision**: 2–3 replicas (`api_min_replicas = 2`), single revision mode. API container 0.5 vCPU / 1 GiB; Collector sidecar 0.25 vCPU / 0.5 GiB. Startup, liveness and readiness probes on `/health/live` and `/health/ready`. (Replaces AKS node pool sizing, per ADR-023.)

**Rationale**: With FR-014's two-replica minimum and single revision mode, a failed new revision never receives traffic while the previous one keeps serving, which is what US4 tests. The 0.75 vCPU / 1.5 GiB total is a valid Consumption combination. The probe paths are the endpoints S4 built; the startup probe allows 60 s for the first start.

**Alternatives considered**:
- *Multiple revision mode with traffic weights*: Gives manual canarying, but a new revision with no ready replicas would receive traffic and drop requests unless weights are managed by hand.
- *`min_replicas = 0`*: Cheapest, but cold starts break the SC-003 latency bar and leave no serving revision during a rollout.
