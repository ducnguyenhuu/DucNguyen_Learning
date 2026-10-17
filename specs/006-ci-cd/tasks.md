# Tasks: CI/CD Pipeline with Performance Verification

**Input**: Design documents from `/specs/006-ci-cd/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Constitution gates**: tenant-isolation tests run inside `integration-test` (`tests/Tenancy.IntegrationTests/Isolation/`). The Quality Gates "Telemetry check" and "Requirement coverage" have no pipeline job in this slice and are tracked as follow-up work, not treated as optional.

**Tests**: Requested only where the plan calls for them: the authorization-policy change (unit + integration, including cross-tenant refusal for the automation identity, US4) and the standing negative proofs in `gate-selftest.yml` (US2). Everything else is verified by running the pipeline itself.

**Organization**: Grouped by user story (US1–US4, priority order). The stories are not independent in time: US2–US4 add jobs to the pipeline US1 creates. Each phase ends at a checkpoint that can be verified on its own.

**Revised context**: The deploy target is Azure Container Apps (ADR-023), not AKS. The pipeline updates the container app's image with `az containerapp update`; it never runs Terraform for the application (research R2, R10).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4, maps to spec.md
- File paths are relative to the repo root

## Authoring vs verification

Like S6, every file-authoring task can be completed **without Azure or GitHub spending anything**. Tasks marked **[AZURE]** need the S6 environment applied to a funded subscription; tasks marked **[GITHUB]** need the repository pushed and a `GITHUB_TOKEN` to apply `infrastructure/github/`. Author first, verify later in one session.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Directory skeletons and provider pins for the two new Terraform roots and the workflows.

- [x] T001 Create `.github/workflows/` with a placeholder `pipeline.yml` containing only the trigger table from contracts/pipeline.md (`pull_request` → `main`, `push` → `main`, `workflow_dispatch`) and `permissions: contents: read`
- [x] T002 [P] Create `infrastructure/github/versions.tf` pinning Terraform ≥ 1.9 and `integrations/github` ~> 6.0, plus an `azurerm` backend block with the partial-config pattern used by S6 and state key `github.tfstate` (contracts/github-config.md → State)
- [x] T003 [P] Create `infrastructure/terraform/persistent/versions.tf` pinning `azurerm` ~> 4.0 and `azuread` ~> 3.0, with its own state key `persistent.tfstate` in the S6 bootstrap storage account (research R2)
- [x] T004 [P] Add `.gitignore` entries for `infrastructure/github/.terraform/`, `infrastructure/terraform/persistent/.terraform/` and the `*.tfvars` files of both roots (their `*.tfvars.example` files stay committed) — already covered by the existing root `.gitignore` rules; verified with `git check-ignore`

**Checkpoint**: `terraform init -backend=false && terraform validate` succeed in both new roots against empty configurations.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The persistent identities and the S6 amendments every story's jobs depend on.

**⚠️ CRITICAL**: US1's `container-publish` and `deploy-dev` cannot run before these exist.

- [x] T005 Create `infrastructure/terraform/persistent/main.tf`: two user-assigned managed identities, `id-github-deployer` and `id-loadtest-client`, each with a federated identity credential for subject `repo:ducnguyenhuu/delivery-intelligent-platform:environment:dev` and audience `api://AzureADTokenExchange` (research R2)
- [x] T006 [P] Create `infrastructure/terraform/persistent/variables.tf` and `outputs.tf`: the repository slug, resource group and location as variables; both identities' client IDs and principal IDs as outputs (they become GitHub variables in T017)
- [x] T007 Amend `infrastructure/terraform/modules/containerapp/app.tf`: add `lifecycle { ignore_changes = [template[0].container[0].image] }` so Terraform owns the app's shape and the pipeline owns the image tag (research R2, R10). Keep the existing empty-tag precondition for first creation
- [x] T008 [P] Amend `infrastructure/scripts/deploy.sh` and `infrastructure/scripts/rollback.sh` so that once the container app exists they run `az containerapp update --image <acr>/tenancy-api:<tag>` instead of `terraform apply -var api_image_tag=...`; keep `terraform apply` only for the first creation path (depends on T007, which would otherwise make the apply a no-op)
- [x] T009 [P] Amend `infrastructure/terraform/modules/apim/api.tf`: replace the single `GET /*` operation with operations for GET, POST, PUT, PATCH and DELETE (`/*`), so load-test seeding can `POST /tenants` (research context, gap 1)
- [x] T010 Amend the S6 root `infrastructure/terraform/main.tf`: role assignments for the deployer — `AcrPush` on the ACR and `Container Apps Contributor` scoped to the one container app — against `id-github-deployer`'s principal ID, looked up with `data "azurerm_user_assigned_identity"` by name and resource group (not `terraform_remote_state`, so `validate` and `plan` need no access to the other root's state; `persistent/` must be applied first) (research R2). No resource-group, subscription or Terraform-state role
- [x] T011 Run `terraform fmt -recursive` and `terraform validate` in `infrastructure/terraform/`, `infrastructure/terraform/persistent/` and `infrastructure/github/`; fix any error

**Checkpoint**: All three Terraform roots validate. `grep -r "Container Apps Contributor" infrastructure/` shows exactly one, app-scoped assignment.

---

## Phase 3: User Story 1 — Commit-to-Dev Automation (Priority: P1) 🎯 MVP

**Goal**: A valid commit to `main` flows build → tests → scans → push → deploy to dev with no manual step, in under 20 minutes, visible stage by stage.

**Independent Test**: Push a trivial valid change to `main`; every job in contracts/pipeline.md up to `deploy-dev` runs unattended, the deployed image tag equals the commit SHA, and `/health/ready` through Front Door returns 200.

### Implementation for User Story 1

- [ ] T012 [P] [US1] Add the `build-test` job to `.github/workflows/pipeline.yml`: `actions/setup-dotnet` with the version from `global.json`, restore, build, unit tests, architecture tests (`tests/Tenancy.UnitTests`, `tests/ArchitectureTests`)
- [ ] T013 [P] [US1] Add the `integration-test` job: `tests/Tenancy.IntegrationTests` against Testcontainers SQL Server 2022, running in parallel with `build-test` (research context; the runner's Docker daemon is used as is)
- [ ] T014 [P] [US1] Add the `container-scan` job: `docker build` once from the repo `Dockerfile`, run `infrastructure/scripts/scan-image-vulnerabilities.sh` and `scan-image-secrets.sh` (including the bait-image negative proof), then save the scanned image as a run artifact (research R10)
- [ ] T015 [US1] Add the `container-publish` job (main only, `environment: dev`, `id-token: write`): supersession guard (R9), `azure/login` with `AZURE_DEPLOYER_CLIENT_ID`, load the scanned image artifact, push `<ACR_LOGIN_SERVER>/tenancy-api:<sha>` — depends on T012–T014
- [ ] T016 [US1] Add the `deploy-dev` job (main only, `environment: dev`, `concurrency: { group: dev-deploy, cancel-in-progress: false }`): guard, preflight `az containerapp show` failing with the contracts/pipeline.md message naming `specs/005-terraform-azure/quickstart.md`, `az containerapp update --image <acr>/tenancy-api:<sha>`, then poll the new revision with `az containerapp revision list` until healthy or 5 minutes elapse, failing the job if it is not (research R10, FR-015) — depends on T015
- [ ] T017 [P] [US1] Create `infrastructure/github/main.tf`, `variables.tf`: environment `dev` (deployment branch `main` only) and the repository variables from contracts/pipeline.md → Inputs (`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_DEPLOYER_CLIENT_ID`, `AZURE_LOADTEST_CLIENT_ID`, `TENANCY_API_APP_ID_URI`, `ACR_LOGIN_SERVER`, `RESOURCE_GROUP`, `CONTAINER_APP_NAME`, `FRONTDOOR_ENDPOINT`) — and **no secrets**; values come from `terraform output` of `persistent/` and the S6 root via a documented one-line `gh variable set` helper in quickstart.md, so no step is undocumented (SC-006)
- [ ] T018 [P] [US1] Add per-job summaries: every job writes a one-line outcome to `$GITHUB_STEP_SUMMARY` and surfaces the first error of a failed step as an `::error::` annotation, via a small shared script or composite action under `.github/` (SC-005, contracts/pipeline.md → Failure semantics)
- [ ] T019 [US1] **[AZURE][GITHUB]** Apply `infrastructure/terraform/persistent/` and the S6 root (amended in Phase 2), apply `infrastructure/github/` with `GITHUB_TOKEN=$(gh auth token)`, then copy the output identifiers into the repository variables (quickstart.md Steps 1–3)
- [ ] T020 [US1] **[AZURE][GITHUB]** Merge a trivial conforming change and verify every job through `deploy-dev` runs unattended, the deployed image equals the commit SHA (`az containerapp show … --query properties.template.containers[0].image`), `curl https://$FRONTDOOR_ENDPOINT/health/ready` returns 200, and the pipeline UI shows per-job status and timing (spec US1 Acceptance Scenarios 1–2)
- [ ] T021 [US1] **[AZURE][GITHUB]** Deliberately fail one gate on a throwaway branch and confirm the failure reason is shown at the top of the run, later jobs never start, and dev keeps serving its previous revision (spec US1 Acceptance Scenario 3)

**Checkpoint**: A commit reaches dev unattended. This is the MVP: the headline roadmap "Done when" (commit → dev in under 20 minutes, fully unattended) can be measured from here.

---

## Phase 4: User Story 2 — Bad Changes Are Rejected Before Reaching Dev (Priority: P2)

**Goal**: An architecture violation, a committed secret, a vulnerable dependency, or a non-conforming commit message each fail the pipeline at the right job with a message naming the rule and location, and the gates keep proving it on a schedule.

**Independent Test**: For each of the four categories, plant a violation on a throwaway branch; the named job fails with the expected message. Restore it and the pipeline passes.

### Implementation for User Story 2

- [ ] T022 [P] [US2] Create `infrastructure/scripts/validate-commit-messages.sh <base> <head>`: checks the first line of every non-merge commit (`git log --no-merges <base>..<head>`) against the grammar in contracts/commit-message.md; prints the offending short SHA, subject and an expected-format example; exits 1 on a violation and 2 on bad arguments (research R5)
- [ ] T023 [P] [US2] Add the `commit-messages` job to `pipeline.yml`, computing `<base>`/`<head>` per contracts/commit-message.md (PR: merge base with `main`; push: previous tip to new tip)
- [ ] T024 [P] [US2] Add the `secret-scan` job: gitleaks over the commit range (PR range; pushed range on `main`), with a weekly full-history run noted for T029 (research R3)
- [ ] T025 [US2] (do this before T012 runs in CI) Amend `Directory.Build.props`: `NuGetAudit=true`, `NuGetAuditMode=all`, `NuGetAuditLevel=high`, and `WarningsAsErrors` including `NU1903;NU1904` (research R4). Run a restore and **upgrade any dependency the audit now flags** rather than lowering the level
- [ ] T026 [P] [US2] Verify the architecture gate reports the rule and file on failure: confirm the existing `tests/ArchitectureTests/` failure messages (see `FAILURE_MESSAGE_AUDIT.md`) are what the `build-test` job surfaces, and add a one-line annotation step if the message is not reaching the job summary (FR-004)
- [ ] T027 [P] [US2] Create `tests/gate-selftest/` with one scratch fixture per rejection: a `Tenancy.Domain`-referencing-`Tenancy.Infrastructure` source file, a generated synthetic secret, a canary project pinned to a package version with a known high-severity advisory, and a `fixed stuff` commit message
- [ ] T028 [US2] Create `.github/workflows/gate-selftest.yml`: runs on pull requests that touch a gate definition, weekly on a schedule, and on `workflow_dispatch`; for each fixture asserts the matching gate **fails** with the expected message (research R11, contracts table) — depends on T022–T027
- [ ] T029 [US2] Add a weekly full-history gitleaks run to `gate-selftest.yml` so a secret merged before the scan existed is caught on the next run (spec Edge Cases, retroactively discovered secrets)
- [ ] T030 [US2] Add a `ruleset` resource to `infrastructure/github/main.tf` per contracts/github-config.md: target `refs/heads/main`, pull request required (0 approvals), required checks `commit-messages`, `secret-scan`, `build-test`, `integration-test`, `container-scan`, branches up to date, no force-push, no deletion, **no bypass actors** (FR-011, research R6)
- [ ] T031 [US2] **[GITHUB]** Apply the ruleset, then attempt a direct push to `main` and confirm it is refused (FR-011)
- [ ] T032 [US2] **[GITHUB]** Run `gate-selftest.yml` on demand and confirm all four proofs fail as expected, then plant each violation on a throwaway branch through the real pipeline and confirm the named job fails with the rule and location (spec US2 Acceptance Scenarios 1–4; SC-002)
- [ ] T033 [US2] **[AZURE][GITHUB]** Confirm a rejected change leaves dev untouched and pushes nothing to ACR (spec US2 Acceptance Scenario 5)

- [ ] T033a [US2] **[AZURE][GITHUB]** Push two commits in quick succession and confirm the older run ends as "cancelled — superseded", then cancel a run during `deploy-dev` and confirm dev keeps serving a healthy revision (FR-014, FR-015, spec Edge Cases)

**Checkpoint**: All four rejection categories are demonstrated failing, repeatedly and on a schedule, and `main` cannot be pushed to directly.

---

## Phase 5: User Story 3 — Production is Gated by Explicit Human Approval (Priority: P3)

**Goal**: A would-deploy-to-production stage pauses for a human reviewer, records who approved, and refuses to proceed when denied or expired. No automation path bypasses it.

**Independent Test**: Run the pipeline on `main`; `production` waits, an approval lets it print the would-deploy record with the approver's identity, a rejection stops it, and an admin cannot bypass it.

### Implementation for User Story 3

- [ ] T034 [US3] Add environment `production` to `infrastructure/github/main.tf`: deployment branch `main` only, one required reviewer (the project owner), `can_admins_bypass = false`, `prevent_self_review` left off for the solo project (research R6)
- [ ] T035 [US3] Add the `production` job to `pipeline.yml` (`needs: deploy-dev` until T046 changes it to `load-test`, `environment: production`): first step fails with `Approval expired — re-run the pipeline for fresh scans` if the triggering commit is more than 7 days old (research R12), then prints the would-deploy record (change author, commit SHA, target environment, run link) to the job summary. It performs **no deployment**
- [ ] T036 [P] [US3] Document the four-eyes limitation: add a *Revisit When* note to `specs/006-ci-cd/research.md` R6 stating that `prevent_self_review` should be enabled when a second human joins
- [ ] T037 [US3] **[GITHUB]** Verify an approval grants and records the approver's identity on the deployment record, a rejection stops the run, and an admin bypass attempt is refused (spec US3 Acceptance Scenarios 1–3; SC-003)
- [ ] T038 [US3] **[GITHUB]** Attempt a post-dev run through each documented trigger (push, `workflow_dispatch`, re-run) without going through the approval and confirm each is refused (spec US3 Acceptance Scenario 4)

**Checkpoint**: The approval gate is wired, tested, and has no bypass.

---

## Phase 6: User Story 4 — Performance Verification Against a Real Environment (Priority: P4)

**Goal**: A load test runs against the deployed dev environment through Front Door and APIM, verifying spec 001 SC-003, with a pass/fail decision from measured p95 and error rate.

**Independent Test**: With a healthy deployment in dev, run the `load-test` job; the summary shows p50/p95/p99 and error rate at 50 virtual users across 20 tenants, and the job passes only if p95 < 1 s and errors < 1%.

### Tests for User Story 4 (the authorization change, written before it)

- [ ] T039 [P] [US4] Add unit tests in `tests/Tenancy.UnitTests/Authorization/` for `CallerAuthorizationPolicy`: accepted — delegated scope `access_as_user`, app role `Tenancy.Automation.Member`; rejected — a token with neither, a token with a different role, a token with an unrelated scope (ADR-022)
- [ ] T040 [P] [US4] Add integration tests in `tests/Tenancy.IntegrationTests/Isolation/`: an application identity holding the automation role is refused on a tenant it is not a member of, with the same response as a user, and can read a tenant it created (Principle IV; ADR-022). Run them and confirm they fail first

### Implementation for User Story 4

- [ ] T041 [US4] Create `src/Tenancy/Tenancy.Api/Authorization/CallerAuthorizationPolicy.cs`: authorized only if the token carries scope `access_as_user` **or** role `Tenancy.Automation.Member`; anything else is rejected (ADR-022)
- [ ] T042 [US4] Amend `src/Tenancy/Tenancy.Api/Program.cs`: make that policy the default authorization policy. Run T039–T040 and the existing suites; all must pass, and no existing test may be weakened to make them pass
- [ ] T043 [US4] Create `infrastructure/terraform/persistent/app-role.tf`: the Tenancy API registration is created by the committed idempotent script `infrastructure/scripts/create-entra-app-registrations.sh` and is not in Terraform, so look it up with `data "azuread_application"` by display name and manage **only** the app role `Tenancy.Automation.Member` (allowed member type: Application) via `azuread_application_app_role`, assigned only to `id-loadtest-client`. Add a note to that script that it must never overwrite `app_role` entries
- [ ] T044 [P] [US4] Create `tests/load/seed.sh`: idempotent seeding per contracts/load-test.md — list tenants the automation identity belongs to, create any missing `loadtest-01`…`loadtest-20` with an `Idempotency-Key` derived from the name, write the 20 tenant IDs to a file k6 reads
- [ ] T045 [P] [US4] Create `tests/load/tenant-reads.js`: k6 scenario per contracts/load-test.md — `warmup` 50 VUs for 30 s (tagged `phase:warmup`), `steady` 50 VUs for 2 min (`phase:steady`), VU *n* uses tenant `n mod 20`, `GET /tenants/{id}` and `GET /tenants/{id}/members` tagged `kind:tenant-read`, 1 s think time, thresholds `p(95)<1000` and `rate<0.01`
- [ ] T046 [US4] Add the `load-test` job to `pipeline.yml` (`needs: deploy-dev`, `environment: dev`; also change the `production` job's `needs` to `load-test`): guard, `azure/login` as `id-loadtest-client`, `az account get-access-token --resource $TENANCY_API_APP_ID_URI`, `seed.sh`, k6 with `--summary-export`, upload `load-test-result`, write the table with the fields in data-model.md §4 (including the one-identity limitation) to the job summary, **no automatic retry**
- [ ] T047 [US4] **[AZURE][GITHUB]** Apply `persistent/app-role.tf`, run the pipeline, and confirm `load-test` passes with p95 < 1 s and error rate < 1% (spec US4 Acceptance Scenarios 1–2)
- [ ] T048 [US4] **[AZURE][GITHUB]** Prove the gate fails: run the load test with a deliberately reduced capacity (e.g. `api_max_replicas` and `min_replicas` temporarily 1 via a throwaway apply) or a tightened threshold, and confirm the job fails naming the breached metric while the preceding deploy stays in dev (spec US4 Acceptance Scenario 3)
- [ ] T049 [US4] Create `docs/operations/load-test-baseline.md` with the measured p50/p95/p99, error rate, sample size, commit SHA and date from T047, and mark spec 001 SC-003 verified in `specs/001-auth-tenant-management/coverage.md`

**Checkpoint**: Spec 001 SC-003 is measured, recorded, and enforced on every run.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Evidence for the success criteria, and closure.

- [ ] T050 **[AZURE][GITHUB]** Time twenty consecutive real runs on `main` and confirm at least 19 (95%) reach dev in under 20 minutes (SC-001); if not, apply the first lever in research R13 (NuGet and Docker layer caching) and re-measure
- [ ] T051 **[GITHUB]** Confirm a new contributor can identify the failing job and reason from the run page in under two minutes on a random failure (SC-005)
- [ ] T052 **[GITHUB]** Confirm a fresh clone plus a fresh GitHub account reproduces the pipeline setup from `quickstart.md` with no undocumented manual step (SC-006)
- [ ] T053 [P] Re-run `terraform validate` in all three roots and a secret scan over `.github/` and `infrastructure/` to confirm the repository holds **zero** secrets (contracts/github-config.md → Repository secrets)
- [ ] T054 [P] Update `roadmap.md`: tick S7's *Done when* items against the evidence from T020–T050, following S5's closure pattern
- [ ] T055 [P] Update `AGENTS.md` (Active Technologies, Recent Changes) and make the "CI validates this on every push" claim in `CLAUDE.md` true by pointing it at `.github/workflows/pipeline.yml`
- [ ] T056 Run S6's `terraform destroy` per the manual cost discipline once verification is complete, leaving `persistent/` and `github/` standing (they cost nothing)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup; blocks US1's publish and deploy jobs
- **US1 (Phase 3)**: after Foundational. MVP
- **US2 (Phase 4)**: after US1's workflow file exists (T012–T016); the gates attach to the same `pipeline.yml`, and the ruleset (T030) names the job names US1 and US2 create
- **US3 (Phase 5)**: after US1. T035 is authored with `needs: deploy-dev`; T046 (US4) then re-points it to `needs: load-test`, so US3 does not wait for US4 and the final order is unchanged
- **US4 (Phase 6)**: after US1's `deploy-dev`; the authorization change (T039–T042) is independent code and can start any time after Setup
- **Polish (Phase 7)**: after all stories

### Within Each Story

- Terraform and workflow authoring before any **[AZURE]**/**[GITHUB]** verification task
- US4: tests T039–T040 written and failing before T041–T042

### Parallel Opportunities

- Setup: T002–T004
- Foundational: T006, T008, T009 (T007 must precede T008's meaning; T010 needs T005's outputs)
- US1: T012, T013, T014, T017, T018 — different jobs and files
- US2: T022, T023, T024, T026, T027
- US4: T039, T040, T044, T045

---

## Parallel Example: User Story 1

```bash
Task: "Add the build-test job to .github/workflows/pipeline.yml"
Task: "Add the integration-test job"
Task: "Add the container-scan job"
Task: "Create infrastructure/github/main.tf with environment dev and the repository variables"
Task: "Add per-job summaries and ::error:: annotations"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup, Phase 2 Foundational
2. Phase 3: the unattended commit-to-dev path
3. **Stop and validate**: a trivial commit reaches dev, in time, with the right image
4. That alone satisfies the roadmap's headline S7 criterion

### Incremental Delivery

1. US1 → commit reaches dev
2. US2 → bad changes rejected, protection as code
3. US3 → approval gate proven
4. US4 → SC-003 measured
5. Polish → ten timed runs, roadmap closure, destroy

### Solo Sequential Strategy (this project's actual mode)

Author every file first (everything not marked **[AZURE]** or **[GITHUB]**), which costs nothing, then verify in one combined session against the funded S6 environment and the pushed repository. Stop at each checkpoint before continuing.

---

## Notes

- Tasks T007 and T008 are the S6 amendment this slice requires (research R2, R10): without `ignore_changes`, the next `terraform apply` reverts the pipeline's image.
- The pipeline never runs `terraform apply` for the application and holds no Terraform state access.
- **Zero repository secrets** is a contract (contracts/github-config.md). If a task seems to need one, the design is wrong.
- Commit after each logical group, following the conventional-commit format the pipeline itself will enforce.
- Every **[AZURE]** task spends real money. Confirm the S6 environment is intended to be up before starting one.
