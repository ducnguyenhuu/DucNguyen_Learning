# Tasks: Terraform → Azure Infrastructure

**Input**: Design documents from `/specs/005-terraform-azure/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not requested for this slice. Verification is via `terraform validate`/`terraform plan`, and the manual end-to-end scenarios in quickstart.md (executed as part of each story's tasks, not as a separate automated test suite).

**Organization**: Tasks are grouped by user story (US1–US4, priority order) so each can be provisioned and verified independently. Setup and Foundational phases provide the shared Terraform/Helm skeleton every story builds on.

**Note on "Phase" numbering (analyze finding M2)**: plan.md's "Phases" section (Phase 1–6: Bootstrap & Networking, Identity & Secrets, Data & Compute, Edge & Routing, Helm & Deploy, Resilience & Teardown) describes *architecture rollout order* — which Azure resource groups get built in what sequence. This file's "Phase 1–7" (Setup, Foundational, US1–US4, Polish) is a *different* numbering scheme for *task grouping* by user story. The two don't align 1:1 (e.g., plan.md Phase 3 "Data & Compute" spans tasks in this file's Phase 2 and Phase 3). Read them as two independent axes, not corresponding steps.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to US1/US2/US3/US4
- File paths are relative to repo root

## Path Conventions

Per plan.md's Project Structure:
- `infrastructure/terraform/` — root Terraform config + `modules/` + `bootstrap/`
- `infrastructure/scripts/` — bootstrap/deploy/rollback Bash scripts
- `infrastructure/helm/tenancy/` — Helm chart
- `specs/005-terraform-azure/` — this feature's docs (already complete from `/speckit.plan`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Terraform/Helm project skeleton exists; provider versions pinned; state backend bootstrapped.

- [X] T001 Create `infrastructure/terraform/versions.tf` pinning `azurerm` (~> 4.0), `azuread` (~> 3.0), `kubernetes`, and `helm` providers, and Terraform ≥ 1.9 (research.md decisions)
- [X] T002 [P] Create `infrastructure/terraform/variables.tf` with all variables from contracts/terraform-variables.md (required + optional, with defaults)
- [X] T003 [P] Create `infrastructure/terraform/outputs.tf` with all outputs from contracts/terraform-variables.md (frontdoor_endpoint, apim_gateway_url, aks_cluster_name, acr_login_server, sql_server_fqdn, keyvault_uri, aks_oidc_issuer_url)
- [X] T004 [P] Create `infrastructure/terraform/dev.tfvars.example` documenting every required variable with placeholder values (never committing real secrets — `new_relic_licence_key` shows `"<set-via-TF_VAR_new_relic_licence_key>"`)
- [X] T005 [P] Create `infrastructure/terraform/bootstrap/main.tf` provisioning the one-time state-storage resource group + storage account + blob container (research.md R1)
- [X] T006 [P] Create `infrastructure/scripts/bootstrap-state.sh` wrapping `az` CLI calls to run the bootstrap config idempotently, printing the storage account name for use in `terraform init -backend-config`
- [X] T007 Create `infrastructure/terraform/main.tf` with the `azurerm` backend block (partial config, keys supplied via `-backend-config` per FR-002/Environment key entity — no Terraform workspaces) and provider blocks
- [X] T008 [P] Add `.gitignore` entries for `infrastructure/terraform/**/.terraform/`, `*.tfstate*`, `*.tfplan`, `dev.tfvars` (real values, as opposed to the committed `.example`)
- [X] T008a Add an `azurerm_resource_group.main` resource to `infrastructure/terraform/main.tf`, named from the new `resource_group_name` variable (contracts/terraform-variables.md) — this is the resource group every module (networking, keyvault, sql, acr, aks, apim, frontdoor) provisions into; without it no module in Phase 2+ can plan or apply (analyze finding C1)

**Checkpoint**: `terraform init` and `terraform validate` succeed against an empty module set. State backend bootstrap is scripted and idempotent.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The networking, identity, and DNS substrate every later resource (SQL, Key Vault, AKS, APIM) attaches to. No user story's resources can be provisioned before this phase completes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every module below is a dependency of at least one story's resources (data-model.md §4).

- [X] T009 Create `infrastructure/terraform/modules/networking/main.tf`: VNet with `vnet_address_space`, and subnets `sn-aks`, `sn-sql-pe`, `sn-kv-pe`, `sn-apim` — takes `resource_group_name` from T008a as an input variable
- [X] T010 [P] Create `infrastructure/terraform/modules/networking/nsg.tf`: NSG on `sn-aks` restricting inbound using the `ApiManagement` regional service tag (FR-007, clarified 2026-09-26 — NOT unrestricted public access). This is a deliberate two-step tightening: the service tag covers every APIM instance in the region and is usable in Phase 2 before any specific APIM instance exists, whereas the actual instance's outbound IP (analyze finding F1) is only known after T031/T032 create it in Phase 4 — see T032a below for the narrowing step
- [X] T011 [P] Create `infrastructure/terraform/modules/networking/dns.tf`: private DNS zones `privatelink.database.windows.net` and `privatelink.vaultcore.azure.net`, both linked to the VNet
- [X] T012 [P] Create `infrastructure/terraform/modules/networking/variables.tf` and `outputs.tf` (subnet IDs, VNet ID, DNS zone IDs)
- [X] T013 [P] Create `infrastructure/terraform/modules/identity/main.tf`: two user-assigned managed identities, `id-tenancy-api` and `id-otel-collector` (data-model.md §2)
- [X] T014 [P] Create `infrastructure/terraform/modules/identity/variables.tf` and `outputs.tf` (identity IDs, principal IDs, client IDs)
- [X] T015 Wire the `networking` and `identity` modules into `infrastructure/terraform/main.tf` (passing `azurerm_resource_group.main.name` from T008a into each) and confirm `terraform plan` succeeds with no other modules yet (Phase 1/2 only)

**Checkpoint**: VNet, subnets, NSG, private DNS zones, and both managed identities exist and plan cleanly. Every subsequent module can now reference their outputs.

---

## Phase 3: User Story 1 - Reproducible Environment from Code (Priority: P1) 🎯 MVP

**Goal**: `terraform apply` into an empty subscription provisions the full resource set with zero portal clicks; `terraform destroy` removes it cleanly; remote state is shared and drift-detectable.

**Independent Test**: Run `terraform apply -var-file=dev.tfvars`, verify every resource exists via `az resource list`, run `terraform destroy -var-file=dev.tfvars`, verify the resource group is empty. This story is testable using only the modules built in this phase — no application deployment required yet (US2 layers on top).

### Implementation for User Story 1

- [X] T016 [P] [US1] Create `infrastructure/terraform/modules/keyvault/main.tf`: Key Vault with private endpoint into `sn-kv-pe`, RBAC-only access mode (no access policies), DNS zone group linking to `privatelink.vaultcore.azure.net`
- [X] T017 [US1] Create `infrastructure/terraform/modules/keyvault/rbac.tf`: `Key Vault Secrets User` role assignments for both `id-tenancy-api` and `id-otel-collector` (depends on T013/T016)
- [X] T018 [US1] Create `infrastructure/terraform/modules/keyvault/secrets.tf`: `new-relic-licence-key` secret, value sourced from the `new_relic_licence_key` sensitive variable — never hardcoded (depends on T016)
- [X] T019 [P] [US1] Create `infrastructure/terraform/modules/sql/main.tf`: Azure SQL Server with `azuread_administrator` block only (Azure AD-only auth, `azuread_authentication_only = true` — research.md R6), private endpoint into `sn-sql-pe`, DNS zone group linking to `privatelink.database.windows.net`
- [X] T020 [US1] Create `infrastructure/terraform/modules/sql/database.tf`: the `sqldb-dip-dev` database on `sql_sku` (default `"Basic"`) (depends on T019)
- [X] T021 [P] [US1] Create `infrastructure/terraform/modules/acr/main.tf`: Container Registry with a globally unique name from `acr_name` variable
- [X] T022 [P] [US1] Create `infrastructure/terraform/modules/aks/main.tf`: `azurerm_kubernetes_cluster` with OIDC issuer enabled, workload identity enabled, CNI Overlay networking (research.md R2), NGINX ingress addon, Key Vault CSI driver addon, into `sn-aks` — its required `default_node_pool` block references the sizing variables defined in T023 (analyze finding M1: the system/initial pool MUST be this inline block, not a separate `azurerm_kubernetes_cluster_node_pool` resource, which the `azurerm` provider reserves for *additional* pools only)
- [X] T023 [US1] Create `infrastructure/terraform/modules/aks/nodepool.tf`: variables/locals for the `default_node_pool` sizing consumed by T022 — `aks_node_vm_size` (default `Standard_B2s`) with cluster autoscaler between `aks_node_count_min`/`aks_node_count_max` (default 1–2), and a pod anti-affinity–friendly topology label set (research.md R8 — spreads FR-014's 2 replicas across nodes). This file holds configuration only; it does not declare a second node-pool resource
- [X] T024 [US1] Create `infrastructure/terraform/modules/aks/rbac.tf`: `AcrPull` role assignment from the AKS kubelet identity to the ACR (depends on T021, T022)
- [X] T025 [US1] Wire `keyvault`, `sql`, `acr`, and `aks` modules into `infrastructure/terraform/main.tf`, passing `azurerm_resource_group.main.name`/networking/identity outputs as inputs (depends on T008a, T009–T024)
- [ ] T026 [US1] Run `terraform validate` and `terraform plan -var-file=dev.tfvars` against the full module set; fix any validation errors
- [ ] T027 [US1] Execute `terraform apply -var-file=dev.tfvars` into the target subscription (quickstart.md Steps 1–3) and record actual apply duration against SC-001's 90-minute budget
- [ ] T028 [US1] Verify remote-state collaboration (spec.md US1 Acceptance Scenario 3): run `terraform plan -var-file=dev.tfvars` from a second checkout/machine and confirm zero changes detected
- [ ] T029 [US1] Execute `terraform destroy -var-file=dev.tfvars` and verify via `az resource list --resource-group rg-dip-dev` that the resource group is empty (quickstart.md Step 9)
- [ ] T030 [US1] Re-run `terraform apply -var-file=dev.tfvars` from scratch and verify `terraform plan -var-file=dev.tfvars -detailed-exitcode` returns 0 (configuration-identical per SC-002, clarified 2026-09-26)

**Checkpoint**: Full infrastructure (networking, identity, Key Vault, SQL, ACR, AKS) provisions and destroys cleanly from code alone, with remote state proven shared and drift-detectable. This is the MVP — infrastructure exists and is reproducible, even though nothing is deployed to it yet.

---

## Phase 4: User Story 2 - Application Reachable Through the Full Request Path (Priority: P2)

**Goal**: The Tenancy API container is deployed to AKS and reachable end-to-end through Front Door → APIM → AKS → SQL, authenticating to both SQL and Key Vault without any stored secret.

**Independent Test**: With US1's infrastructure standing, build and push the container image, deploy via Helm, then `curl` the Front Door URL's `/health/live` and `/health/ready` and confirm both return 200 — the latter proving the managed-identity SQL connection works.

### Implementation for User Story 2

- [X] T031 [P] [US2] Create `infrastructure/terraform/modules/apim/main.tf`: APIM instance on `apim_sku` (default `Developer_1`), **not** VNet-integrated (research.md R3, clarified 2026-09-26)
- [X] T032 [US2] Create `infrastructure/terraform/modules/apim/api.tf`: API definition with backend pointing at the AKS ingress controller's public IP/FQDN (depends on T022's AKS output)
- [ ] T032a [US2] Narrow the Phase-2 NSG rule (T010) from the broad `ApiManagement` service tag to this specific APIM instance's actual outbound public IP, now that T031/T032 have created it — update `infrastructure/terraform/modules/networking/nsg.tf`'s rule source to reference the APIM module's outbound IP output (depends on T031)
- [X] T033 [P] [US2] Create `infrastructure/terraform/modules/frontdoor/main.tf`: Front Door Standard profile + endpoint on the `*.azurefd.net` managed domain (research.md R5)
- [X] T034 [US2] Create `infrastructure/terraform/modules/frontdoor/routing.tf`: origin group pointing at the APIM gateway URL, route for `/*`, managed TLS certificate (depends on T031)
- [X] T035 [US2] Wire `apim` and `frontdoor` modules into `infrastructure/terraform/main.tf` (depends on T025, T031–T034)
- [ ] T036 [US2] Run `terraform apply -var-file=dev.tfvars` to provision APIM + Front Door on top of the standing US1 infrastructure; record actual APIM apply duration against the 30–45 min estimate
- [X] T037 [P] [US2] Create `infrastructure/helm/tenancy/Chart.yaml` and `infrastructure/helm/tenancy/values.yaml` per contracts/helm-values.md defaults (api.replicas: 2, rollout.maxUnavailable: 0/maxSurge: 1 — FR-014)
- [X] T038 [P] [US2] Create `infrastructure/helm/tenancy/values-dev.yaml` per contracts/helm-values.md dev overrides (image repository, workload identity client-id placeholders, `ConnectionStrings__DefaultConnection` using `Authentication=Active Directory Default`)
- [X] T039 [P] [US2] Create `infrastructure/helm/tenancy/templates/serviceaccount.yaml` for `tenancy-api`, annotated with `azure.workload.identity/client-id` and the AKS OIDC federated-credential label
- [X] T040 [P] [US2] Create `infrastructure/helm/tenancy/templates/deployment.yaml`: Tenancy API Deployment with `replicas: 2`, `strategy.rollingUpdate.maxUnavailable: 0`/`maxSurge: 1` (FR-014), liveness probe on `/health/live`, readiness probe on `/health/ready`, resource requests/limits from values
- [X] T041 [P] [US2] Create `infrastructure/helm/tenancy/templates/service.yaml` (ClusterIP) and `infrastructure/helm/tenancy/templates/ingress.yaml` (NGINX ingress class, host from `ingress.host`)
- [X] T042 [P] [US2] Create `infrastructure/helm/tenancy/templates/configmap.yaml` for non-secret Tenancy API config and `infrastructure/helm/tenancy/templates/_helpers.tpl` for shared template functions
- [X] T043 [US2] Create `infrastructure/terraform/modules/identity/federation.tf` binding the `tenancy-api` Kubernetes service account (namespace `default`) to `id-tenancy-api` via the AKS OIDC issuer URL from T022's output (depends on T022, T039)
- [X] T044 [P] [US2] Create `infrastructure/scripts/deploy.sh`: `docker build` → `infrastructure/scripts/scan-image-vulnerabilities.sh` + `scan-image-secrets.sh` (existing S5 Trivy scripts — fail the script on any unresolved high/critical finding, per Constitution Quality Gates) → `az acr login` → `docker tag` → `docker push` → `helm upgrade --install` sequence (quickstart.md Step 5–6, analyze finding D1)
- [ ] T045 [US2] Run `infrastructure/scripts/deploy.sh` to build/scan/push the existing S5 Dockerfile image and deploy it via Helm; confirm the scan step actually ran and passed before push (depends on T037–T044)
- [ ] T046 [US2] Verify `kubectl get pods` shows 2 Ready replicas and `curl "$FRONTDOOR_URL/health/live"` returns 200 (spec.md US2 Acceptance Scenario 1)
- [ ] T047 [US2] Verify `curl "$FRONTDOOR_URL/health/ready"` returns 200, proving the managed-identity SQL connection succeeds with no connection-string secret anywhere (spec.md US2 Acceptance Scenario 2) — cross-check via `kubectl get secrets -o yaml | grep -i "password\|connection"` returning nothing (SC-004)
- [ ] T048 [US2] Verify the Key Vault CSI driver mounts the New Relic licence key into the OTel Collector pod via workload identity, with the secret value absent from any Helm value, ConfigMap, or manifest (spec.md US2 Acceptance Scenario 3) — this task only proves the *mounting*; end-to-end telemetry delivery is US3's concern
- [ ] T048a [US2] Time 10 sequential `curl -o /dev/null -w "%{time_total}\n"` calls to `"$FRONTDOOR_URL/health/ready"` and confirm every sample is under 2 seconds (spec.md SC-003, analyze finding E1 — previously uncovered)

**Checkpoint**: A real HTTP request traverses Front Door → APIM → AKS → SQL and returns healthy, using only managed/workload identity for backend authentication. US1 + US2 together prove the infrastructure and the first deployed, reachable, secretless application.

---

## Phase 5: User Story 3 - Telemetry Flows from Azure to New Relic (Priority: P3)

**Goal**: The OTel Collector runs in AKS, reads the New Relic licence key from Key Vault via workload identity, and forwards correlated traces from the deployed application to New Relic.

**Independent Test**: With US2's deployed application standing, trigger a few requests through Front Door, then confirm in New Relic's Distributed Tracing view that a trace for service `Tenancy.Api` appears within 60 seconds, and independently confirm the licence key never appears in logs, files, or manifests.

### Implementation for User Story 3

- [X] T049 [P] [US3] Create `infrastructure/helm/tenancy/templates/otel-collector.yaml`: OTel Collector Deployment (image `otel/opentelemetry-collector-contrib`, 1 replica per contracts/helm-values.md), Service exposing ports 4317/4318, ServiceAccount annotated for workload identity
- [X] T050 [US3] Extend `infrastructure/terraform/modules/identity/federation.tf` (created in T043) with a second federated-credential block binding the `otel-collector` Kubernetes service account → `id-otel-collector` via the AKS OIDC issuer (depends on T043, T049)
- [X] T051 [US3] Create `infrastructure/helm/tenancy/templates/secretproviderclass.yaml`: Key Vault CSI `SecretProviderClass` mounting `new-relic-licence-key` as `NEW_RELIC_LICENCE_KEY`, referencing `keyVault.vaultName`/`tenantId` from values (depends on T018)
- [X] T052 [US3] Adapt `deploy/otel-collector/config.yaml` into `infrastructure/helm/tenancy/templates/otel-collector-configmap.yaml`, adding an `otlphttp` exporter pointed at New Relic's OTLP endpoint, with the licence key read from the mounted CSI secret file rather than an env var literal (research.md — telemetry backend per ADR-018)
- [X] T053 [US3] Wire the OTel Collector's exporter endpoint into the Tenancy API's Helm values (`OTEL_EXPORTER_OTLP_ENDPOINT` → the in-cluster `otel-collector` Service) so application traces flow through the freshly-deployed collector, not the local S4/S5 collector
- [ ] T054 [US3] Redeploy via `infrastructure/scripts/deploy.sh` (or `helm upgrade`) to pick up the OTel Collector templates and updated Tenancy API env vars
- [ ] T055 [US3] Trigger several requests through the Front Door URL and verify in New Relic Distributed Tracing that a correlated `Tenancy.Api` trace appears within 60 seconds (spec.md US3 Acceptance Scenario 1 / SC-005)
- [ ] T056 [US3] Verify the licence key is never logged, never written to a file readable outside the CSI mount, and never present in any Kubernetes manifest or Helm value (spec.md US3 Acceptance Scenario 2 / SC-004) — check `kubectl logs deployment/otel-collector` and `helm get values tenancy` for leakage

**Checkpoint**: Telemetry from the deployed application flows through Azure into New Relic, with the licence key sourced exclusively via workload identity + Key Vault CSI. US1 + US2 + US3 together prove the full observable, deployed, identity-secured path.

---

## Phase 6: User Story 4 - Broken Rollout Recovery (Priority: P4)

**Goal**: A deliberately broken deployment is detected by AKS health probes without dropping traffic (FR-014's 2-replica/`maxUnavailable: 0` guarantee), and the operator recovers via rollback within the SC-006 budget.

**Independent Test**: With US2's healthy deployment standing, deploy a nonexistent image tag, confirm existing replicas keep serving 200s throughout (no dropped requests), then `helm rollback` and confirm full recovery within 5 minutes.

### Implementation for User Story 4

- [X] T057 [P] [US4] Create `infrastructure/scripts/rollback.sh`: wraps `helm rollback tenancy <revision>` plus a `kubectl rollout status` wait, per quickstart.md Step 8
- [ ] T058 [US4] Execute the broken-rollout scenario from quickstart.md Step 8: start a background poll of `$FRONTDOOR_URL/health/live`, deploy `--set api.image.tag=nonexistent-tag`, and confirm via `kubectl get pods` that existing replicas stay Ready while new ones sit in `ImagePullBackOff` (depends on T046, T057)
- [ ] T059 [US4] Confirm the background poll from T058 recorded zero non-200 responses throughout the failed rollout (spec.md US4 Acceptance Scenario 1 — validates FR-014's zero-dropped-traffic guarantee)
- [ ] T060 [US4] Run `infrastructure/scripts/rollback.sh` to roll back to the previous healthy revision and verify `kubectl rollout status deployment/tenancy-api` reports success and `$FRONTDOOR_URL/health/live` returns 200 within 2 minutes (spec.md US4 Acceptance Scenario 2 / SC-006)

**Checkpoint**: All four user stories are independently provisioned, deployed, observed, and proven resilient. The environment is ready for the final teardown/rebuild and documentation polish.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification sweep, documentation, and requirement-coverage closure across all stories.

- [ ] T061 [P] Run the SC-004 automated secret scan from quickstart.md Step 7c (`kubectl get secrets`, `grep` across `infrastructure/helm/`) and confirm zero matches
- [ ] T062 [P] Run the edge-case check for stale APIM outbound IP ranges (spec.md Edge Cases): re-apply the `networking` module's NSG rule and confirm `terraform plan` shows it as re-appliable without manual intervention
- [ ] T063 Execute the full teardown/rebuild cycle (quickstart.md Steps 9–10): `terraform destroy`, verify empty resource group, `terraform apply` again, verify `terraform plan -detailed-exitcode` returns 0 (SC-002 final confirmation across the complete module set, not just US1's subset)
- [ ] T064 [P] Update `docs/operations/` with a `azure-environment.md` (or similar) summarizing the provisioned topology, referencing data-model.md, and recording actual measured durations (apply, APIM provisioning, rollback recovery) against SC-001/SC-006
- [ ] T065 [P] Update `roadmap.md`: mark S6's "Done when" checklist items against the verified evidence from T027–T063, following the same pattern as S5's closure
- [ ] T066 [P] Update `AGENTS.md`'s Active Technologies section to reflect the final (not draft) module list and any decisions that changed during implementation (e.g., if R3's public-IP-with-NSG approach needed adjustment)
- [ ] T067 Final `terraform destroy` to leave the subscription empty between sessions, per the manual cost-control discipline (spec.md Assumptions, clarified 2026-09-26)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories (networking/identity outputs are consumed by every module in US1–US4)
- **User Story 1 (Phase 3)**: Depends on Foundational. This is the MVP — infrastructure exists and is reproducible.
- **User Story 2 (Phase 4)**: Depends on US1's standing infrastructure (AKS, ACR, SQL must exist to deploy into/against them). Not parallelizable with US1's `terraform apply`, but its Helm-chart file creation (T037–T042) can proceed in parallel with US1's later verification tasks (T027–T030) since they touch different files.
- **User Story 3 (Phase 5)**: Depends on US2's deployed application (needs a running Tenancy API generating traces, and the AKS OIDC issuer from US1).
- **User Story 4 (Phase 6)**: Depends on US2's deployed, healthy application and its FR-014 2-replica configuration (built in US2's T040).
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### User Story Dependencies

Unlike a typical application feature, these stories are **sequential by necessity**, not just priority — each layers physically on top of the previous story's provisioned resources (US2 deploys into US1's AKS; US3 instruments US2's running pods; US4 breaks US2's deployment). This differs from the tasks-template's usual "stories are independent" pattern; the story boundaries here mark *independently verifiable checkpoints* along one build-out, not parallel workstreams for different team members.

### Within Each User Story

- Terraform modules before Helm charts (US2 needs AKS/ACR from US1 to exist)
- Helm chart files ([P] tasks, different files) before the `helm upgrade --install` that consumes them
- Deployment before verification (apply/deploy tasks before their corresponding `curl`/`kubectl` checks)

### Parallel Opportunities

- All Setup tasks marked [P] (T002–T006, T008) can run in parallel — different files, no cross-dependencies
- Within Foundational, T010–T014 can run in parallel once T009 (VNet) exists
- Within US1, T016, T019, T021, T022 (the four leaf modules: keyvault, sql, acr, aks) can be authored in parallel — each depends only on Phase 2 outputs, not on each other
- Within US2, the Helm chart file tasks T037–T042 can all run in parallel — different files, no dependencies between them
- Within US3, T049 and T051 can run in parallel (different template files) before T052 (which references both)

---

## Parallel Example: User Story 1

```bash
# Author all four leaf Terraform modules together (different directories, no cross-deps):
Task: "Create infrastructure/terraform/modules/keyvault/main.tf"
Task: "Create infrastructure/terraform/modules/sql/main.tf"
Task: "Create infrastructure/terraform/modules/acr/main.tf"
Task: "Create infrastructure/terraform/modules/aks/main.tf"
```

## Parallel Example: User Story 2 (Helm chart authoring)

```bash
Task: "Create infrastructure/helm/tenancy/Chart.yaml and values.yaml"
Task: "Create infrastructure/helm/tenancy/values-dev.yaml"
Task: "Create infrastructure/helm/tenancy/templates/serviceaccount.yaml"
Task: "Create infrastructure/helm/tenancy/templates/deployment.yaml"
Task: "Create infrastructure/helm/tenancy/templates/service.yaml + ingress.yaml"
Task: "Create infrastructure/helm/tenancy/templates/configmap.yaml + _helpers.tpl"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1 — reproducible infrastructure, apply/destroy/rebuild proven
4. **STOP and VALIDATE**: `terraform plan` is clean after rebuild; resource group is genuinely empty after destroy
5. This alone satisfies the roadmap's "Terraform + remote state + one dev environment" build items and de-risks the ~$700–1,500/month cost question before any application deploy is attempted

### Incremental Delivery

1. Setup + Foundational → shared substrate ready
2. US1 → infrastructure reproducible → **checkpoint**: cost/apply-time reality-check against SC-001 before proceeding
3. US2 → application reachable end-to-end, secretless → **checkpoint**: the core "it works in Azure" proof
4. US3 → telemetry closes the observability loop → **checkpoint**: S4's instrumentation validated against a real backend
5. US4 → resilience proven → **checkpoint**: roadmap's explicit "AKS is not learned until this" bar cleared
6. Polish → documentation, roadmap closure, final teardown

### Solo Sequential Strategy (this project's actual mode)

Given the sequential dependency structure noted above, work proceeds phase-by-phase rather than with parallel team members. Within each phase, the [P]-marked file-creation tasks can still be batched to reduce round-trips, but the `terraform apply`/`helm upgrade` tasks that follow them are hard checkpoints — do not start the next story's provisioning until the current story's verification tasks pass.

---

## Notes

- [P] tasks = different files, no dependencies — safe to author in one batch
- [Story] label maps task to specific user story for traceability back to spec.md
- This slice's "independent test" per story means "independently *verifiable checkpoint*," not "independently deployable in isolation from earlier stories" — see the Dependencies section's note on sequential build-out
- Commit after each module/template file or logical group, consistent with S5's practice
- Every `terraform apply`/`destroy` is a real-money operation against a live Azure subscription — confirm `dev.tfvars` values before running T027, T029, T030, T036, T063, T067
- Stop at any checkpoint to validate against the corresponding spec.md acceptance scenarios before continuing
- Avoid: skipping the T026 `terraform plan` review before T027's `apply`; hand-editing anything in the Azure portal (violates FR-001 and Constitution Technology Constraints)
