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

**Rationale**: VNet integration is what lets the app reach Azure SQL and Key Vault through their private endpoints and the existing private DNS zones. A Consumption-only environment needs a `/23` and no subnet delegation, and carries no fixed node cost, unlike a workload-profiles environment with a dedicated profile. External ingress is required because Front Door Standard reaches its origin over the public network (R3, R5).

**Alternatives considered**:
- *Workload profiles environment*: `/27` minimum and dedicated-profile pricing; no benefit for one small service in dev.
- *Internal-only environment*: Cleaner, but Front Door Standard cannot reach it; that needs Front Door Premium with Private Link (see ADR-024, Revisit When).
- *Environment outside the VNet*: Cannot use the SQL and Key Vault private endpoints, failing FR-006.

## R3 — No API Management; public ingress behind Front Door

**Decision** (ADR-024, 2026-10-20): API Management is not provisioned. The container app's ingress is public with no source restriction, and Front Door is the intended way in. *(Originally: APIM Developer tier, not VNet-integrated, reaching the app's public ingress through an IP allow-list of APIM's outbound addresses.)*

**Rationale**: APIM Developer was the largest fixed cost (~$50/month) and took 30–45 minutes per apply, for features nothing in Horizon 1 uses: the API validates Entra tokens itself and there are no per-consumer policies. The IP allow-list existed only to admit APIM; Front Door's backend addresses are a service tag, which Container Apps ingress restrictions cannot express. Every endpoint except the health probes still requires a valid token (ADR-022), so the exposure is the health endpoints.

**Alternatives considered**:
- *APIM Consumption tier*: ~$0 idle and quick to provision, but no fixed outbound IPs and no consumer for its features.
- *Keep APIM Developer*: fixed cost and apply time with no consumer (Principle X).
- *Enforce Front Door as the only path*: the `X-Azure-FDID` header check in the API, or Front Door Premium with Private Link to an internal environment. Deferred (ADR-024, Revisit When).

## R4 — Managed Identity for ACR, SQL and Key Vault

**Decision**: Two **user-assigned managed identities** attached to the one container app: `id-tenancy-api` (ACR pull, Azure SQL) and `id-otel-collector` (Key Vault secret read). The licence key is a Container Apps **Key Vault secret reference** (`key_vault_secret_id` + identity), mounted into the collector sidecar as a **file** via a `Secret` volume. (Replaces AKS workload identity federation + Key Vault CSI, per ADR-023.)

**Rationale**: No federation, OIDC issuer or service-account wiring exists, and the two-phase apply the AKS design needed disappears. Mounting the secret as a file keeps the SC-004 property that the key is never an environment variable. Separate identities keep least privilege on the Azure side even though both run in one app.

**Alternatives considered**:
- *System-assigned identity*: One identity for everything; cannot separate ACR/SQL from Key Vault access and is recreated on every destroy.
- *Secret as an environment variable (`secretRef`)*: Simpler, but makes the licence key an environment variable in the process, which US3 forbids.
- *Direct Key Vault SDK calls*: Needs application code changes and does not help the Collector.

**Open risk**: The Key Vault has public access disabled. Whether the Container Apps platform resolves the secret reference through the private endpoint (and whether Terraform can write the secret from outside the VNet) is unverified until the first apply.

## R5 — Front Door directly in front of Container Apps

**Decision**: Front Door Standard with the container app's ingress FQDN as the origin. Front Door handles TLS termination on `*.azurefd.net`, optional WAF, and health-probed routing to the origin. *(Originally APIM was the origin; removed by ADR-024.)*

**Rationale**: Front Door provides edge TLS and routing, which is all this topology needs. In dev its global distribution is unnecessary, but it proves the wiring and the edge that production would use.

**Alternatives considered**:
- *Front Door → APIM → Container Apps*: the original design; see R3 for why APIM was dropped.
- *Azure Application Gateway*: Regional only; Front Door is the prescribed component in idea.md §17.

## R6 — Azure SQL Authentication Mode

**Decision**: Azure AD-only authentication. SQL Server is provisioned with `azuread_authentication_only = true`. The Tenancy API's managed identity is granted `db_datareader` and `db_datawriter` roles. No SQL auth login exists.

**Rationale**: Constitution Principle V prohibits stored credentials. Azure AD-only auth eliminates the SA password entirely — there is no SQL auth fallback to accidentally expose. The managed identity used by the application authenticates via Azure AD token, with no connection string containing a password.

**Alternatives considered**:
- *Mixed mode (SQL + Azure AD)*: Allows fallback to SA password, which is a secret that must be managed and can leak.
- *Azure AD auth with SQL admin fallback*: Common but violates the "no stored credentials" principle for database access.

## R7 — Terraform-managed Container App vs Helm / Kubernetes manifests

**Decision**: The container app is an `azurerm_container_app` resource in the `containerapp` Terraform module. A deploy is a `terraform apply` that changes `api_image_tag`; there is no Helm chart or manifest set. (Replaces the Helm decision, per ADR-023.)

**Rationale**: Terraform owns the app's shape and ignores its image tag (amended for S7), so a deploy is an `az containerapp update` and a later apply never reverts it. ADR-012's "Terraform provisions, Helm deploys" split disappears with Kubernetes. Revisions give release history, and recovery is redeploying a known-good tag.

**Alternatives considered**:
- *`az containerapp update` with `ignore_changes` on the image*: Avoids a full apply per deploy, but creates exactly the drift this decision avoids.
- *Bicep/ARM for the app only*: A second IaC language for no benefit.

**Consequence**: The first-ever apply is two-step, because the app cannot be created without an image already in ACR: `terraform apply -target=module.acr`, then `deploy.sh`. A precondition on the app fails the plan with a clear message if `api_image_tag` is empty.

## R8 — Replicas, Probes and Sizing

**Decision**: 1–3 replicas (`api_min_replicas = 1`), single revision mode. API container 0.5 vCPU / 1 GiB; Collector sidecar 0.25 vCPU / 0.5 GiB. Startup, liveness and readiness probes on `/health/live` and `/health/ready`. (Replaces AKS node pool sizing, per ADR-023.)

**Rationale**: With single revision mode (FR-014, amended 2026-10-20 from a two-replica minimum), a failed new revision never receives traffic while the previous one keeps serving, which is what US4 tests. The 0.75 vCPU / 1.5 GiB total is a valid Consumption combination. The probe paths are the endpoints S4 built; the startup probe allows 60 s for the first start.

**Alternatives considered**:
- *Multiple revision mode with traffic weights*: Gives manual canarying, but a new revision with no ready replicas would receive traffic and drop requests unless weights are managed by hand.
- *`min_replicas = 0`*: Cheapest, but cold starts break the SC-003 latency bar and leave no serving revision during a rollout.
