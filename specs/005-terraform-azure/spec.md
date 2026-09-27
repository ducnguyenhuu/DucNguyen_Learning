# Feature Specification: Terraform → Azure Infrastructure

**Feature Branch**: `005-terraform-azure`  
**Created**: 2026-09-26  
**Status**: Draft  
**Input**: User description: "start S6 nhé"

## Clarifications

### Session 2026-09-26

- Q: US4's acceptance scenario requires the previous healthy version to keep serving traffic while a broken deployment is detected — but a single-replica default would cause a brief outage during rollout regardless of the deployment's health. Should the environment require ≥2 replicas with `maxUnavailable: 0`? → A: Require ≥2 replicas with `maxUnavailable: 0` — old pods keep serving until new ones are Ready; zero-downtime rollback is real
- Q: Since APIM Developer tier isn't VNet-integrated, how should APIM reach AKS's ingress controller? → A: Public ingress IP on AKS, restricted via NSG to APIM's published outbound IP ranges — cheap, still access-controlled
- Q: SC-002 says `terraform destroy` + `terraform apply` produces a "bit-for-bit identical environment" — but Azure assigns new resource IDs/IPs on every fresh apply, so this is never literally achievable. What does "identical" mean? → A: Configuration-identical: same resource types/SKUs/settings/topology; verified by a clean `terraform plan` (no diff) against the same `.tfvars` after a fresh apply
- Q: The "Environment" key entity says it's distinguished by "Terraform workspace or variable file" — which mechanism? → A: Separate `.tfvars` file per environment, single fixed state key per environment — no Terraform workspaces
- Q: Should the system automatically detect or prevent runaway Azure spend (given the ~$700–1,500/month footprint), or does cost control stay a manual discipline? → A: No automated budget enforcement — manual `terraform destroy` discipline

## User Scenarios & Testing

### User Story 1 — Reproducible Environment from Code (Priority: P1)

An operator provisions the entire platform infrastructure into an empty Azure subscription by running a single Terraform command. No portal clicks, no manual DNS entries, no hand-created secrets. The resulting environment is identical every time, and tearing it down with `terraform destroy` leaves no orphaned resources or billable remnants.

**Why this priority**: This is the foundational promise of the slice — if infrastructure is not code-reproducible, nothing else (deploy, telemetry, identity) can be trusted. It also directly controls cost: the ~$700–1,500/month footprint must be destroyable between sessions.

**Independent Test**: Run `terraform apply` against an empty subscription, verify all resources exist and are configured correctly, then run `terraform destroy` and confirm zero resources remain.

**Acceptance Scenarios**:

1. **Given** an empty Azure subscription with no pre-existing resources, **When** an operator runs `terraform apply` with the required variables, **Then** all infrastructure resources are provisioned without error and without portal interaction.
2. **Given** a fully provisioned environment, **When** the operator runs `terraform destroy`, **Then** all resources are removed and the subscription returns to its empty state with no orphaned resources or ongoing charges.
3. **Given** the Terraform state is stored remotely, **When** a second operator (or the same operator on a different machine) runs `terraform plan`, **Then** no changes are detected — the remote state reflects reality.

---

### User Story 2 — Application Reachable Through the Full Request Path (Priority: P2)

A user's request flows through the complete production-grade networking topology: Azure Front Door → API Management → AKS → Azure SQL. Health endpoints respond correctly through this path, proving that DNS, TLS, routing, ingress, and service wiring all function end-to-end.

**Why this priority**: Provisioning resources is necessary but not sufficient. This story proves the resources are wired together correctly — the first real request through the stack.

**Independent Test**: Deploy the container image manually (no CI/CD pipeline) to AKS, then issue an HTTP request to the Front Door endpoint and verify a healthy response from the application.

**Acceptance Scenarios**:

1. **Given** the infrastructure is provisioned and the application is deployed to AKS, **When** a request hits the Front Door URL at `/health/live`, **Then** it returns 200 Healthy, having traversed Front Door → APIM → AKS.
2. **Given** the application is running in AKS, **When** it queries Azure SQL for tenant data, **Then** the connection succeeds using managed identity — no connection-string secret exists in any manifest, environment variable, or Kubernetes secret.
3. **Given** the application needs a configuration secret (e.g. the New Relic ingest licence key), **When** it reads from Key Vault, **Then** it authenticates via workload identity — the secret value never appears in a manifest or deployment artifact.

---

### User Story 3 — Telemetry Flows from Azure to New Relic (Priority: P3)

Traces, metrics, and logs from the application running in AKS are collected by the OTel Collector (also running in AKS) and forwarded to New Relic. The New Relic ingest licence key is read from Key Vault by the collector via workload identity — it never appears in a Helm chart, ConfigMap, or any checked-in file.

**Why this priority**: Observability was built in S4, but this is the first time it runs in a real cloud environment. Proving the telemetry pipeline works end-to-end in Azure closes the loop between "instrumented locally" and "observable in production."

**Independent Test**: Trigger a request through the deployed application, then verify in New Relic that correlated traces appear with the expected service name, tenant enrichment, and span attributes.

**Acceptance Scenarios**:

1. **Given** the application and OTel Collector are running in AKS, **When** a request completes through the API, **Then** a correlated trace appears in New Relic within 60 seconds.
2. **Given** the OTel Collector is configured to read the New Relic licence key from Key Vault, **When** the collector starts, **Then** it authenticates via workload identity and the licence key is never logged, never written to a file on disk, and never present in any Kubernetes manifest.

---

### User Story 4 — Broken Rollout Recovery (Priority: P4)

An operator deliberately deploys a broken version of the application to AKS. The cluster detects the failure (health probes fail, pods don't become Ready), and the operator recovers by rolling back. This proves that the health probes, readiness gates, and rollback mechanism work before a real incident demands them.

**Why this priority**: The roadmap explicitly states "AKS is not learned until this." A platform that can deploy but cannot recover from a bad deploy is incomplete.

**Independent Test**: Push a known-bad image tag to AKS, observe the rollout stall, then rollback and verify the previous healthy version resumes serving traffic.

**Acceptance Scenarios**:

1. **Given** a healthy application is running in AKS with at least 2 replicas and a `maxUnavailable: 0` rollout strategy, **When** a deployment references a non-existent or crashing image, **Then** AKS detects the failure via health probes and does not route traffic to the broken pods — the existing healthy replicas continue serving throughout, with zero dropped requests.
2. **Given** a failed rollout is in progress, **When** the operator issues a rollback command, **Then** the previous healthy version resumes serving and health endpoints return 200 within 2 minutes.

---

### Edge Cases

- What happens when Terraform state and real infrastructure drift (e.g., someone deletes a resource in the portal)? The next `terraform plan` must detect the drift and propose to re-create the missing resource.
- What happens when `terraform apply` is interrupted mid-way (e.g., network failure during the 30–45 min APIM provisioning)? A subsequent `terraform apply` must recover gracefully without orphaned resources.
- What happens when the Azure subscription hits a quota or spending limit? Terraform must fail with a clear error rather than creating a partial environment.
- What happens when the New Relic licence key is rotated in Key Vault? The OTel Collector must pick up the new key on its next restart without redeployment.
- What happens when private endpoint DNS resolution fails? The application must produce a clear, diagnosable error rather than hanging on connection timeout.
- What happens when Azure's published APIM outbound IP ranges change? The NSG rule restricting AKS ingress access must be re-appliable from Terraform without manual intervention, and a stale rule must fail visibly (403/timeout) rather than silently allowing broader access.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provision all infrastructure resources (AKS, ACR, APIM, Front Door, Azure SQL, Key Vault, OTel Collector, networking) from Terraform code with no manual portal configuration.
- **FR-002**: The system MUST store Terraform state remotely in Azure Storage, enabling multiple operators to collaborate on the same environment.
- **FR-003**: The system MUST provision exactly one environment (`dev`) with dev/test SKUs to minimise cost while remaining functionally representative of production topology — concretely, the same resource types and routing path as production (Front Door → APIM → AKS → SQL), sized down per SKU/replica count, and meeting SC-003's latency bar despite the smaller scale.
- **FR-004**: The system MUST configure managed identity for Azure SQL access — no connection-string secrets in any manifest, environment variable, or Kubernetes object.
- **FR-005**: The system MUST configure workload identity for Key Vault access by both the application and the OTel Collector — secret values never appear in deployment artifacts.
- **FR-006**: The system MUST configure private endpoints for Azure SQL and Key Vault, keeping data-plane traffic off the public internet.
- **FR-007**: The system MUST route external traffic through Front Door → APIM → AKS ingress, with TLS termination at Front Door. AKS ingress MAY use a public IP (APIM Developer tier is not VNet-integrated) but MUST restrict inbound access via network security group rules to APIM's published outbound IP ranges only.
- **FR-008**: The system MUST deploy the OTel Collector to AKS, configured to forward telemetry to New Relic, with the ingest licence key sourced from Key Vault via workload identity.
- **FR-009**: The system MUST produce a Helm chart (or Kubernetes manifests) that deploys the Tenancy API container to AKS with health probes mapped to the existing `/health/live` and `/health/ready` endpoints.
- **FR-010**: The system MUST support `terraform destroy` that removes all provisioned resources cleanly, returning the subscription to its pre-apply state.
- **FR-011**: The system MUST detect and report infrastructure drift — a `terraform plan` after manual changes must show the discrepancy.
- **FR-012**: The system MUST support a manual first deploy (no CI/CD pipeline) that proves the full request path works end-to-end.
- **FR-013**: The system MUST support rollback of a failed AKS deployment to the previous healthy version.
- **FR-014**: The Tenancy API deployment MUST run at least 2 replicas with a `maxUnavailable: 0` rollout strategy, so a broken deployment never drops traffic — the previous healthy replicas continue serving until the new replicas pass health checks or the rollout is rolled back.

### Key Entities

- **Environment**: A named deployment target (e.g., `dev`) with its own set of Azure resources, distinguished by a dedicated `.tfvars` file and a fixed remote-state key (e.g., `dev.tfstate`) — not by Terraform workspaces.
- **Remote State**: The Terraform state file stored in Azure Storage, serving as the single source of truth for what infrastructure exists.
- **Workload Identity Federation**: The binding between a Kubernetes service account and an Azure AD managed identity, enabling pods to authenticate to Azure services without secrets.
- **Helm Release**: A versioned deployment of the application and its dependencies (OTel Collector) to AKS, parameterised by environment-specific values.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A new team member can provision the entire environment from an empty subscription in under 90 minutes (including the ~30–45 min APIM provisioning time), following only the written quickstart guide — no tribal knowledge required.
- **SC-002**: `terraform destroy` followed by `terraform apply` produces a configuration-identical environment — same resource types, SKUs, settings, and topology (not identical resource IDs or IP addresses, which Azure reassigns on every fresh apply) — verified by a clean `terraform plan` showing zero diffs against the same `.tfvars`.
- **SC-003**: End-to-end request latency through Front Door → APIM → AKS → SQL completes in under 2 seconds for health-check requests.
- **SC-004**: Zero secrets (connection strings, licence keys, passwords) appear in any checked-in file, Kubernetes manifest, or deployment artifact — verified by automated scan.
- **SC-005**: Telemetry from a deployed request appears in New Relic within 60 seconds of the request completing.
- **SC-006**: Recovery from a deliberately broken deployment completes in under 5 minutes from detection to healthy traffic resuming.

## Assumptions

- Cost control for the ~$700–1,500/month footprint is a manual operator discipline (running `terraform destroy` between sessions per the roadmap) — this slice does not build automated budget alerting or spend caps.
- An Azure subscription is available and funded (the open decision noted in the roadmap — sandbox or Azure for Students credit, with the understanding that $100 credit does not cover the full footprint).
- The Entra ID tenant and app registrations from S2 are reusable — the subscription and the Entra tenant may be different, as noted in the roadmap.
- The container image from S5 (Tenancy API on `noble-chiseled-extra`) is available and can be pushed to ACR.
- The OTel Collector configuration from S4 can be adapted for AKS deployment with minimal changes (primarily swapping the exporter endpoint from local to New Relic OTLP).
- A New Relic account with an active ingest licence key is available.
- DNS for Front Door will use Azure-managed subdomains (e.g., `*.azurefd.net`) for dev — custom domains are deferred to production environments.

## Scope Boundaries

**In scope**: Everything listed under "Build" in the roadmap S6 section — Terraform, remote state, `dev` environment, ACR, AKS, APIM, Front Door, Azure SQL, Key Vault, OTel Collector on AKS, managed + workload identity, private endpoints, Helm chart, first manual deploy, broken rollout recovery.

**Out of scope**:
- CI/CD pipeline automation (S7)
- Service Bus (S8)
- QA or production environments
- Azure AI Search (no consumer until after Gate 2)
- Log Analytics / Application Insights as a telemetry backend (telemetry backend is New Relic per ADR-018)
- Custom DNS domains (dev uses Azure-managed subdomains)

## Dependencies

- **S2 (Auth + Tenant)**: Entra ID app registrations and tenant configuration
- **S4 (Observability)**: OTel Collector configuration and telemetry pipeline design
- **S5 (Containerization)**: Docker image, health probes, graceful shutdown behaviour
- **ADR-001**: Azure as primary cloud
- **ADR-007**: AKS and full target architecture in Horizon 1
- **ADR-012**: Terraform for all infrastructure
- **ADR-018**: New Relic as telemetry backend
