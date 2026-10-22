# Implementation Plan: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26, revised 2026-10-16 for Container Apps (ADR-023) | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-terraform-azure/spec.md`

## Summary

Provision the full `idea.md` §17 target architecture into Azure using Terraform: Container Apps, ACR, Front Door, Azure SQL, Key Vault, private endpoints, managed identity, and the OTel Collector (as a sidecar) — all from code, reproducible into an empty subscription. The Tenancy API container from S5 is deployed as a Terraform-managed container app, observable through New Relic, and proven recoverable from a deliberately broken revision.

## Technical Context

**Language/Version**: HCL (Terraform ≥ 1.9) for infrastructure; Bash for orchestration scripts
**Primary Dependencies**: azurerm provider (~> 4.0), azuread provider (~> 3.0)
**Storage**: Azure Storage Account (Terraform remote state); Azure SQL (application data)
**Testing**: `terraform validate`, `terraform plan` (drift detection), manual end-to-end verification per quickstart.md
**Target Platform**: Azure (West US 2 or East US 2 — closest regions with all required services)
**Project Type**: Infrastructure-as-code
**Performance Goals**: Health-check round-trip through full path < 2s
**Constraints**: Dev/test SKUs only; teardown/rebuild must be reliable; cost to be re-estimated for Container Apps (the ~$700–1,500/month figure assumed AKS and is withdrawn)
**Scale/Scope**: Single `dev` environment; 1 Container Apps environment, 1 container app (2–3 replicas); 1 SQL database

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [X] **I — Human approval retained**: Production deployment is out of scope (dev only). Azure subscription funding requires human decision. No automated deployment path — first deploy is manual.
- [X] **II — ADRs identified**: ADR-001 (Azure), ADR-007 (full topology in H1), ADR-023 (Container Apps, not AKS), ADR-012 (Terraform), ADR-018 (New Relic). No conflicts — this slice implements what those ADRs decided.
- [X] **III — Service boundaries respected**: Single service (Tenancy API) with its own database. OTel Collector is infrastructure, not a service boundary violation.
- [X] **IV — Tenant isolation**: Unchanged from S2. Azure SQL connection via managed identity preserves the existing EF Core tenant filter. No new data access path introduced.
- [X] **V — No stored credentials**: Managed identity for SQL; managed identity for Key Vault. Connection strings with passwords prohibited. New Relic licence key lives in Key Vault, never in code or manifests.
- [X] **VI — Observable by default**: OTel Collector deployed as a Container Apps sidecar, forwarding to New Relic. Existing instrumentation from S4 unchanged — only the exporter destination changes.
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
│   └── container-app.md        # Container app contract (replaces the Helm values contract)
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
│   │   ├── networking/          # VNet, subnets, private DNS zones
│   │   ├── containerapp/        # Container Apps environment + app (API + OTel sidecar)
│   │   ├── acr/                 # Container registry
│   │   ├── sql/                 # Azure SQL server + database + private endpoint
│   │   ├── keyvault/            # Key Vault + private endpoint + secrets
│   │   ├── frontdoor/           # Front Door profile + endpoint + origin group + route
│   │   └── identity/            # User-assigned managed identities
│   └── bootstrap/
│       └── main.tf              # One-time: storage account for remote state
└── scripts/
    ├── bootstrap-state.sh       # Create the state storage account
    ├── deploy.sh                # Manual first deploy: build → scan → push ACR → terraform apply
    └── rollback.sh              # Recovery helper: redeploy a known-good image tag
```

**Structure Decision**: Terraform modules are grouped by Azure resource type, not by environment. Environment differentiation is via `.tfvars` files. The container app is itself a Terraform resource (ADR-023), so there is no chart or manifest directory. The OTel Collector is a sidecar container in the same app since it serves only this application in `dev`.

## Complexity Tracking

No constitution violations to justify. The module count (8) is driven by Azure resource types, each with distinct lifecycle and private endpoint wiring — not over-engineering. Dropping AKS removed a module, a chart and two providers.

## Phases

### Phase 1 — Bootstrap & Networking (Foundation)

**Goal**: Remote state backend exists; VNet and subnets are provisioned; private DNS zones are configured.

1. Bootstrap script creates the Azure Storage Account for Terraform remote state (one-time, outside Terraform's own state).
2. Root Terraform config (`main.tf`) with azurerm backend pointing to that storage.
3. Networking module: VNet with subnets for the Container Apps environment (`/23`), the SQL private endpoint and the Key Vault private endpoint. There is no NSG, and no source restriction at the container app: Front Door reaches a public ingress (FR-007, ADR-024).
4. Private DNS zones for `privatelink.database.windows.net` and `privatelink.vaultcore.azure.net`.

### Phase 2 — Identity & Secrets

**Goal**: Managed identities exist; Key Vault is provisioned with private endpoint.

1. Identity module: user-assigned managed identity for the Tenancy API; user-assigned managed identity for the OTel Collector.
2. Key Vault module: Key Vault with private endpoint, RBAC access (no access policies), secrets seeded (New Relic licence key).

### Phase 3 — Data & Compute

**Goal**: Azure SQL, ACR and the Container Apps environment are provisioned, connected via private endpoint and managed identity.

1. SQL module: Azure SQL Server (Azure AD-only auth, no SQL auth), database, private endpoint.
2. ACR module: Container registry. The `AcrPull` grant for `id-tenancy-api` lives in the containerapp module.
3. Container Apps environment (Consumption-only, VNet-integrated). The container app itself is created in Phase 5, once an image exists.

### Phase 4 — Edge & Routing

**Goal**: Front Door routes traffic to the container app.

1. Front Door module: Standard tier profile, endpoint, origin group pointing to the container app's FQDN, route for `/*`.
2. TLS: Front Door managed certificate on the `*.azurefd.net` domain.

### Phase 5 — Deploy

**Goal**: Application and OTel Collector running as one container app, reachable through the full path.

1. `terraform apply -target=module.acr`, then `deploy.sh` builds, scans, pushes the image and runs the full apply with `api_image_tag` set.
2. Container app: Tenancy API container with probes (`/health/live` for startup and liveness, `/health/ready` for readiness), single revision mode, 2–3 replicas (FR-014).
3. OTel Collector sidecar: config adapted from S4's `config.yaml` (env var `OTEL_COLLECTOR_CONFIG`), `otlphttp` exporter for New Relic, licence key mounted as a file from a Key Vault secret reference.
4. End-to-end verification: request through Front Door → Container Apps → SQL; trace appears in New Relic.

### Phase 6 — Resilience & Teardown

**Goal**: Broken revision recovery proven; clean teardown verified.

1. Recovery test: deploy a known-bad image tag against the ≥2-replica app (FR-014), observe the new revision fail while the old one keeps serving with zero dropped requests, run `rollback.sh <known-good-tag>`, verify recovery.
2. `terraform destroy` removes everything; verify subscription is empty.
3. Full cycle: `terraform apply` again from scratch, verify configuration-identical environment via `terraform plan -detailed-exitcode` (SC-002 — not literally identical resource IDs/IPs).

## Global Constraints

- **No portal clicks**: Every resource is Terraform-managed. Manual changes are drift.
- **No secrets in code**: All secrets sourced from Key Vault via managed identity. The `.env` pattern from S5 local dev does not apply to Azure.
- **Dev/test SKUs only**: Consumption-only Container Apps, SQL Basic, Front Door Standard. Cost control is a first-class concern.
- **Idempotent operations**: `terraform apply` (including image-tag changes) must be safe to re-run.
- **Existing tests must pass**: The 266-test suite from S5 continues to pass. No application code changes are expected; only infrastructure and deployment files are added.
