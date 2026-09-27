# Research: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

## R1 — Terraform State Backend Bootstrap

**Decision**: A separate `infrastructure/terraform/bootstrap/` Terraform config (or a Bash script using `az` CLI) creates the Azure Storage Account, container, and resource group for remote state. This runs once, manually, before the main `terraform init`.

**Rationale**: Terraform cannot manage its own state backend — the storage account must exist before `terraform init` configures the backend. This is the standard chicken-and-egg pattern. A small bootstrap script is simpler than a separate Terraform config for one resource group + one storage account.

**Alternatives considered**:
- *Terraform Cloud / HCP*: Adds a third-party dependency and cost. Azure Storage is simpler and Azure-native (ADR-001).
- *Local state*: Violates FR-002 (multi-operator collaboration) and is dangerous for shared infrastructure.
- *ARM template for bootstrap*: Works but introduces a second IaC language for no benefit.

## R2 — AKS Networking Model

**Decision**: Azure CNI Overlay networking. AKS nodes get VNet IPs; pods get overlay IPs from a separate CIDR managed by AKS.

**Rationale**: CNI Overlay is the recommended default for new AKS clusters. It avoids the subnet IP exhaustion problem of classic Azure CNI (where every pod consumes a VNet IP), while still supporting Network Policies, private endpoints, and VNet integration. Kubenet is being deprecated. Classic Azure CNI requires careful subnet sizing.

**Alternatives considered**:
- *Classic Azure CNI*: Requires large subnets (IP per pod). Over-provisions for dev, complicates subnet planning.
- *Kubenet*: Deprecated path; no Network Policy support without third-party CNI; UDR management overhead.
- *Azure CNI with dynamic IP allocation*: More complex than Overlay for no dev-environment benefit.

## R3 — APIM SKU and VNet Integration

**Decision**: APIM Developer tier, **not** VNet-integrated. APIM connects to AKS via the AKS ingress controller's **public IP**, restricted by a network security group to APIM's published outbound IP ranges (clarified 2026-09-26, spec.md FR-007 — see also §"NGINX ingress" below; superseded the earlier "public or internal LB" open question).

**Rationale**: APIM VNet integration (internal or external mode) requires the Premium tier (~$2,800/month) or the newer stv2 platform on Developer tier with significant provisioning time (45–60 min). For dev, the simpler approach is APIM Developer tier calling AKS's ingress endpoint directly, with the NSG rule as the compensating control so the "last hop" isn't wide open to the internet. The networking still proves the routing topology (Front Door → APIM → AKS) without the Premium cost.

**Alternatives considered**:
- *APIM Premium with full VNet integration*: Proves private networking but costs ~$2,800/month for dev — far exceeds the $700–1,500 budget for the entire environment.
- *APIM Basic*: Cheaper but lacks developer portal and some policy features useful for learning.
- *Skip APIM*: Violates the roadmap's explicit inclusion and the target architecture in idea.md §17.
- *Public ingress IP, unrestricted*: Simplest, but leaves the AKS ingress open to the entire internet, not just APIM — rejected during clarification in favor of the NSG-restricted option.

**Correction (if needed)**: If Developer tier stv2 supports VNet injection at dev cost, prefer that. Verify during implementation.

## R4 — Workload Identity for Key Vault Access

**Decision**: Azure Workload Identity (federated identity credentials on user-assigned managed identities) with the Azure Key Vault CSI driver for Kubernetes.

**Rationale**: Workload Identity is the successor to AAD Pod Identity (deprecated). It uses Kubernetes service account token projection + OIDC federation to Azure AD, with no cluster-level infrastructure component. The Key Vault CSI driver mounts secrets as volumes, avoiding the need for application code changes — the OTel Collector reads the New Relic licence key from a mounted file, and the Tenancy API can similarly access Key Vault secrets.

**Alternatives considered**:
- *AAD Pod Identity (v1)*: Deprecated; requires NMI daemonset; known race conditions.
- *Direct SDK calls from app to Key Vault*: Works but requires application code changes and doesn't help the OTel Collector (which is configured via files/env vars, not SDK calls).
- *Kubernetes Secrets synced from Key Vault*: Introduces a sync delay and a second copy of the secret in etcd.

## R5 — Front Door + APIM Integration Pattern

**Decision**: Front Door Standard tier with APIM as the origin. Front Door handles TLS termination on `*.azurefd.net`, WAF (optional), and global load balancing. APIM handles API policies, rate limiting, and backend routing.

**Rationale**: This is the documented Microsoft pattern for the enterprise API gateway topology. Front Door provides edge TLS and caching; APIM provides API management. In dev, Front Door's global distribution is unnecessary but proves the wiring and the topology that production would use.

**Alternatives considered**:
- *Front Door directly to AKS*: Skips APIM, losing the API management layer the roadmap requires.
- *APIM as the sole edge*: No CDN/WAF/global distribution. Works for dev but doesn't prove the target topology.
- *Azure Application Gateway*: Regional only; Front Door is the prescribed component in idea.md §17.

## R6 — Azure SQL Authentication Mode

**Decision**: Azure AD-only authentication. SQL Server is provisioned with `azuread_authentication_only = true`. The Tenancy API's managed identity is granted `db_datareader` and `db_datawriter` roles. No SQL auth login exists.

**Rationale**: Constitution Principle V prohibits stored credentials. Azure AD-only auth eliminates the SA password entirely — there is no SQL auth fallback to accidentally expose. The managed identity used by the application authenticates via Azure AD token, with no connection string containing a password.

**Alternatives considered**:
- *Mixed mode (SQL + Azure AD)*: Allows fallback to SA password, which is a secret that must be managed and can leak.
- *Azure AD auth with SQL admin fallback*: Common but violates the "no stored credentials" principle for database access.

## R7 — Helm Chart vs Raw Kubernetes Manifests

**Decision**: Helm chart under `infrastructure/helm/tenancy/`.

**Rationale**: Helm provides templating for environment-specific values (`values-dev.yaml`), atomic rollback via `helm rollback`, release history, and a standard packaging format. The chart bundles the Tenancy API deployment and the OTel Collector as related deployments within one release, which simplifies the deploy/rollback lifecycle for dev.

**Alternatives considered**:
- *Kustomize*: Good for overlays but lacks release management (rollback, history). The rollback story (US4) is simpler with Helm.
- *Raw manifests with `kubectl apply`*: No templating, no rollback, no release tracking. Fine for learning but insufficient for FR-013.
- *ArgoCD / Flux (GitOps)*: Over-engineering for dev with manual deploys; belongs in S7 (CI/CD) if adopted.

## R8 — AKS Node Pool Sizing

**Decision**: Single system node pool, `Standard_B2s` (2 vCPU, 4 GiB), 1–2 nodes with cluster autoscaler.

**Rationale**: The Tenancy API container is ~69 MB, needs minimal CPU/memory. The OTel Collector similarly lightweight. B-series is burstable and cheapest for dev workloads with low sustained CPU. Autoscaler 1–2 ensures availability during node updates while minimising idle cost. With FR-014's 2-replica requirement (clarified 2026-09-26), a pod anti-affinity rule should spread the 2 API replicas across nodes when the autoscaler is at 2 nodes, so a single node failure does not take down both replicas simultaneously — the 2-node ceiling exists partly to make this possible, not just for update headroom.

**Alternatives considered**:
- *Standard_D2s_v5*: More consistent performance but ~2× the cost of B2s. Not needed for dev.
- *Spot instances*: Cheapest but can be evicted — inappropriate for the only node pool.
- *Larger nodes, fewer count*: Single node is a SPOF during updates. 1–2 with autoscaler is the minimum viable setup.
