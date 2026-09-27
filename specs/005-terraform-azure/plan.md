# Implementation Plan: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-terraform-azure/spec.md`

## Summary

Provision the full `idea.md` §17 target architecture into Azure using Terraform: AKS, ACR, APIM, Front Door, Azure SQL, Key Vault, private endpoints, managed/workload identity, and the OTel Collector — all from code, reproducible into an empty subscription. The Tenancy API container from S5 is deployed via Helm, observable through New Relic, and proven recoverable from a deliberately broken rollout.

## Technical Context

**Language/Version**: HCL (Terraform ≥ 1.9) for infrastructure; Helm 3 for Kubernetes packaging; Bash for orchestration scripts
**Primary Dependencies**: azurerm provider (~> 4.0), azuread provider (~> 3.0), kubernetes provider, helm provider
**Storage**: Azure Storage Account (Terraform remote state); Azure SQL (application data)
**Testing**: `terraform validate`, `terraform plan` (drift detection), manual end-to-end verification per quickstart.md
**Target Platform**: Azure (West US 2 or East US 2 — closest regions with all required services)
**Project Type**: Infrastructure-as-code + Kubernetes manifests
**Performance Goals**: Health-check round-trip through full path < 2s; APIM apply < 45 min
**Constraints**: Dev/test SKUs only; teardown/rebuild must be reliable; ~$700–1,500/month budget
**Scale/Scope**: Single `dev` environment; 1 AKS node pool (1–2 nodes); 1 SQL database

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [X] **I — Human approval retained**: Production deployment is out of scope (dev only). Azure subscription funding requires human decision. No automated deployment path — first deploy is manual.
- [X] **II — ADRs identified**: ADR-001 (Azure), ADR-007 (AKS in H1), ADR-012 (Terraform), ADR-018 (New Relic). No conflicts — this slice implements what those ADRs decided.
- [X] **III — Service boundaries respected**: Single service (Tenancy API) with its own database. OTel Collector is infrastructure, not a service boundary violation.
- [X] **IV — Tenant isolation**: Unchanged from S2. Azure SQL connection via managed identity preserves the existing EF Core tenant filter. No new data access path introduced.
- [X] **V — No stored credentials**: Managed identity for SQL; workload identity for Key Vault. Connection strings with passwords prohibited. New Relic licence key lives in Key Vault, never in code or manifests.
- [X] **VI — Observable by default**: OTel Collector deployed to AKS, forwarding to New Relic. Existing instrumentation from S4 unchanged — only the exporter destination changes.
- [X] **VII — Automated gates**: Architecture tests from S3 still run. Container image scanning from S5 still applies to ACR images. `terraform validate` gates malformed HCL. Drift detection via `terraform plan`.
- [X] **VIII — Deterministic first**: No AI capabilities in this slice.
- [X] **IX — AI abstraction**: No AI capabilities in this slice.
- [X] **X — Vertical slice**: Delivers working, deployed, observable software through the full Azure path. Proven by the end-to-end request and the broken rollout recovery.
- [X] **XI — No individual measurement**: Not applicable to infrastructure provisioning.

## Project Structure

### Documentation (this feature)

```text
specs/005-terraform-azure/
├── plan.md              # This file
├── research.md          # Phase 0: technical decisions
├── data-model.md        # Phase 1: infrastructure resource model
├── quickstart.md        # Phase 1: step-by-step provisioning guide
├── contracts/
│   ├── terraform-variables.md   # Required input variables
│   └── helm-values.md          # Helm chart value contract
├── checklists/
│   └── requirements.md         # Spec quality checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
infrastructure/
├── terraform/
│   ├── main.tf                  # Root module: provider config, backend, module calls
│   ├── variables.tf             # Input variables
│   ├── outputs.tf               # Outputs (FQDN, resource IDs, connection info)
│   ├── versions.tf              # Required providers and versions
│   ├── dev.tfvars               # Dev environment variable values
│   ├── modules/
│   │   ├── networking/          # VNet, subnets, private DNS zones, NSGs
│   │   ├── aks/                 # AKS cluster, node pool, OIDC issuer
│   │   ├── acr/                 # Container registry
│   │   ├── sql/                 # Azure SQL server + database + private endpoint
│   │   ├── keyvault/            # Key Vault + private endpoint + secrets
│   │   ├── apim/                # API Management instance + API definitions
│   │   ├── frontdoor/           # Front Door profile + endpoint + origin group + route
│   │   └── identity/            # Managed identities + workload identity federation
│   └── bootstrap/
│       └── main.tf              # One-time: storage account for remote state
├── scripts/
│   ├── bootstrap-state.sh       # Create the state storage account
│   ├── deploy.sh                # Manual first deploy: build → push ACR → helm upgrade
│   └── rollback.sh              # AKS rollback helper
└── helm/
    └── tenancy/
        ├── Chart.yaml
        ├── values.yaml              # Default values
        ├── values-dev.yaml          # Dev overrides
        └── templates/
            ├── deployment.yaml      # Tenancy API deployment
            ├── service.yaml         # ClusterIP service
            ├── ingress.yaml         # NGINX ingress (AKS addon)
            ├── hpa.yaml             # Horizontal pod autoscaler (optional)
            ├── serviceaccount.yaml  # With workload identity annotations
            ├── configmap.yaml       # Non-secret config
            ├── otel-collector.yaml  # OTel Collector deployment + service + configmap
            └── _helpers.tpl         # Template helpers
```

**Structure Decision**: Terraform modules are grouped by Azure resource type, not by environment. Environment differentiation is via `.tfvars` files. The Helm chart lives under `infrastructure/helm/` because it is deployment infrastructure, not application code. The OTel Collector is bundled into the same Helm chart as a sidecar/companion deployment since it serves only this application in `dev`.

## Complexity Tracking

No constitution violations to justify. The module count (8) is driven by Azure resource types, each with distinct lifecycle and private endpoint wiring — not over-engineering.

## Phases

### Phase 1 — Bootstrap & Networking (Foundation)

**Goal**: Remote state backend exists; VNet and subnets are provisioned; private DNS zones are configured.

1. Bootstrap script creates the Azure Storage Account for Terraform remote state (one-time, outside Terraform's own state).
2. Root Terraform config (`main.tf`) with azurerm backend pointing to that storage.
3. Networking module: VNet with subnets for AKS, SQL private endpoint, Key Vault private endpoint. An NSG on the AKS ingress subnet restricts inbound traffic to APIM's published outbound IP ranges (FR-007) — APIM Developer tier itself is not VNet-integrated (research.md R3).
4. Private DNS zones for `privatelink.database.windows.net` and `privatelink.vaultcore.azure.net`.

### Phase 2 — Identity & Secrets

**Goal**: Managed identities exist; Key Vault is provisioned with private endpoint; workload identity federation is configured.

1. Identity module: user-assigned managed identity for the Tenancy API; user-assigned managed identity for the OTel Collector.
2. Key Vault module: Key Vault with private endpoint, RBAC access (no access policies), secrets seeded (New Relic licence key).
3. Workload identity federation bindings: Kubernetes service accounts → Azure managed identities via OIDC issuer.

### Phase 3 — Data & Compute

**Goal**: Azure SQL and AKS are provisioned, connected via private endpoint and managed identity.

1. SQL module: Azure SQL Server (Azure AD-only auth, no SQL auth), database, private endpoint, managed identity as admin.
2. ACR module: Container registry, AKS pull permissions.
3. AKS module: Cluster with OIDC issuer enabled, workload identity enabled, NGINX ingress addon, single node pool (Standard_B2s or Standard_D2s_v5 dev/test), AcrPull role assignment.

### Phase 4 — Edge & Routing

**Goal**: Front Door and APIM route traffic to AKS.

1. APIM module: Developer-tier instance, API definition importing the Tenancy API's OpenAPI spec (or passthrough proxy).
2. Front Door module: Standard tier profile, endpoint, origin group pointing to APIM, route for `/`.
3. TLS: Front Door managed certificate on the `*.azurefd.net` domain.

### Phase 5 — Helm & Deploy

**Goal**: Application and OTel Collector running in AKS, reachable through the full path.

1. Helm chart: Tenancy API deployment with health probes (`/health/live` for liveness, `/health/ready` for readiness), service account with workload identity annotations, resource limits, 2 replicas with `maxUnavailable: 0` rollout strategy (FR-014).
2. OTel Collector: deployment with config adapted from S4's `config.yaml`, adding `otlphttp` exporter for New Relic, Key Vault CSI driver for the licence key.
3. Deploy script: `docker build` → `docker tag` → `az acr login` → `docker push` → `helm upgrade --install`.
4. End-to-end verification: request through Front Door → APIM → AKS → SQL; trace appears in New Relic.

### Phase 6 — Resilience & Teardown

**Goal**: Broken rollout recovery proven; clean teardown verified.

1. Rollback test: deploy a known-bad image against a ≥2-replica, `maxUnavailable: 0` deployment (FR-014), observe the new replicas fail while old replicas keep serving with zero dropped requests, execute `helm rollback`, verify recovery.
2. `terraform destroy` removes everything; verify subscription is empty.
3. Full cycle: `terraform apply` again from scratch, verify configuration-identical environment via `terraform plan -detailed-exitcode` (SC-002 — not literally identical resource IDs/IPs).

## Global Constraints

- **No portal clicks**: Every resource is Terraform-managed. Manual changes are drift.
- **No secrets in code**: All secrets sourced from Key Vault via workload identity or managed identity. The `.env` pattern from S5 local dev does not apply to Azure.
- **Dev/test SKUs only**: AKS Basic/Free, SQL Basic, APIM Developer, Front Door Standard. Cost control is a first-class concern.
- **Idempotent operations**: `terraform apply` and `helm upgrade --install` must be safe to re-run.
- **Existing tests must pass**: The 266-test suite from S5 continues to pass. No application code changes are expected; only infrastructure and deployment files are added.
