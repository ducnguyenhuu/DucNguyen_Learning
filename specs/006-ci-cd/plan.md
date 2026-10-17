# Implementation Plan: CI/CD Pipeline with Performance Verification

**Branch**: `006-ci-cd` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/006-ci-cd/spec.md`

## Summary

Build the project's first CI/CD pipeline on GitHub Actions: every pull request runs the full gate
set (commit messages, secrets, dependency advisories, build, unit/integration/architecture tests,
container image scans); every merge to `main` additionally publishes the scanned image to ACR,
deploys it to the S6 dev environment, and runs a k6 load test that verifies spec 001 SC-003. A
no-op `production` stage proves the human-approval gate. The pipeline holds **zero secrets** —
Azure access is OIDC-federated to managed identities — and each rejection gate is re-proven by a
standing self-test that plants a violation and asserts failure.

The one change to application code is an explicit authorization policy (ADR-022, accepted 2026-09-29) that
lets a single named automation identity be a tenant member, so the load test can authenticate
without a stored credential.

## Technical Context

**Language/Version**: GitHub Actions workflow YAML; Bash for gate scripts; JavaScript (k6) for the load test; HCL (Terraform ≥ 1.9) for identities and repository configuration; C# 14 / .NET 10 for the authorization-policy change
**Primary Dependencies**: GitHub Actions (`actions/checkout`, `actions/setup-dotnet`, `azure/login`, `grafana/setup-k6-action`), gitleaks, Trivy (existing S5 scripts), NuGet Audit (built into the .NET SDK), Terraform providers `azurerm` ~> 4.0, `azuread` ~> 3.0, `integrations/github` ~> 6.0
**Storage**: No new application storage. Pipeline evidence lives in GitHub (run history, job summaries, deployment records, artifacts); the SC-003 measurement is copied into `docs/operations/load-test-baseline.md` as the permanent record
**Testing**: Existing xUnit v3 suites run in the pipeline; `gate-selftest.yml` proves each rejection gate fails on a planted violation; new unit + integration tests for the authorization policy, including cross-tenant refusal for the automation identity
**Target Platform**: GitHub-hosted `ubuntu-latest` runners → Azure (S6 dev environment: ACR, Container Apps, APIM, Front Door)
**Project Type**: CI/CD configuration + infrastructure-as-code + one small application change
**Performance Goals**: Commit → dev in < 20 min on 95% of runs (SC-001); spec 001 SC-003 — p95 tenant read < 1 s at 50 concurrent users across 20 tenants, error rate < 1% (SC-004)
**Constraints**: Zero repository secrets (Principle V); no approval bypass for admins or automation (Principle I); never cancel mid-deploy (FR-014); deployment target may be torn down between sessions (S6 cost discipline)
**Scale/Scope**: One repository, one protected branch, two environments (`dev`, `production` stub), two federated identities, ~2 workflows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [X] **I — Human authority**: `production` environment requires a human reviewer with `can_admins_bypass = false`; the pipeline cannot approve itself. ADR-022 changes the authorization surface; the project owner accepted it on 2026-09-29.
- [X] **II — ADRs identified, conflicts proposed**: Relies on ADR-001, 007, 012, 013, 017, 018, 019. Raises and records **ADR-022** (application identities as tenant members, accepted). Two S6 defects found (APIM `GET`-only, and an image tag Terraform would otherwise keep reverting) are proposed as explicit amendments, not worked around.
- [X] **III — Service/data boundaries**: No new service, no new data store. The automation identity reaches data only through the API, never the database (which is private-endpoint-only anyway).
- [X] **IV — Tenant isolation**: The automation identity is an ordinary member of the tenants it creates and nothing more. New tests prove it is refused on tenants it does not belong to, identically to a user.
- [X] **V — No stored credentials**: OIDC federation for every Azure call; the repository holds variables (identifiers), no secrets. The authorization change *narrows* accepted tokens to an explicit allow-list. Secret scanning is added for source (gitleaks) and kept for images (S5).
- [X] **VI — Observable by default**: No new request paths. Load-test traffic flows through the S4 instrumentation to New Relic, tenant-enriched as usual; the automation identity is visible in telemetry by its `oid`.
- [X] **VII — Automated gates**: This slice *is* Principle VII's pipeline: build, unit, integration, architecture, secret, dependency, and image gates all fail the build — and each rejection is re-proven by `gate-selftest.yml`. It also makes `CLAUDE.md`'s currently-false "CI validates this on every push" true.
- [X] **VIII — Deterministic first**: No AI.
- [X] **IX — AI abstraction**: No AI.
- [X] **X — Vertical slice**: Delivers a working, observable path from commit to deployed dev environment, verified end-to-end by the load test. Depends on S6 being applied — see Phase 0 below.
- [X] **XI — No individual measurement**: Pipeline metrics describe the system (duration, gate outcomes, latency), never an individual developer.

## Project Structure

### Documentation (this feature)

```text
specs/006-ci-cd/
├── plan.md              # This file
├── research.md          # R1–R13 decisions
├── data-model.md        # Where each spec entity lives
├── quickstart.md        # One-time setup, negative proofs, approval test, SC-003 verification
├── contracts/
│   ├── pipeline.md          # Triggers, jobs, required checks, permissions, failure semantics
│   ├── load-test.md         # Scenario, seeding, thresholds, result schema
│   ├── github-config.md     # Ruleset, environments, variables — and the explicit empty secret list
│   └── commit-message.md    # Accepted grammar and merge-commit handling
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
.github/
└── workflows/
    ├── pipeline.yml             # PR + push to main: gates → publish → deploy dev → load test → production stub
    └── gate-selftest.yml        # Negative proofs for all four rejection gates (R11)

infrastructure/
├── terraform/
│   ├── persistent/              # NEW root, own state key — survives S6 destroy cycles (R2)
│   │   ├── main.tf              # 2 managed identities + GitHub federated credentials
│   │   ├── app-role.tf          # Tenancy.Automation.Member app role + assignment (ADR-022)
│   │   ├── variables.tf
│   │   └── outputs.tf           # Client IDs → copied into GitHub variables by infrastructure/github
│   ├── main.tf                  # AMENDED: role assignments for the deployer against current ACR/container app
│   └── modules/
│       ├── containerapp/app.tf  # AMENDED: ignore_changes on the container image (R2, R10)
│       └── apim/api.tf          # AMENDED: operations for all methods, not GET only
├── github/                      # NEW root, own state key (R6)
│   ├── main.tf                  # Ruleset on main, environments dev + production, variables
│   ├── variables.tf
│   └── versions.tf
└── scripts/
    └── validate-commit-messages.sh   # NEW (R5)

tests/
└── load/
    ├── tenant-reads.js          # k6 scenario + thresholds (R8)
    └── seed.sh                  # Idempotent: ensures 20 loadtest tenants exist, via the API

src/Tenancy/Tenancy.Api/
├── Authorization/
│   └── CallerAuthorizationPolicy.cs  # NEW: scp=access_as_user OR roles∋Tenancy.Automation.Member (ADR-022)
└── Program.cs                        # AMENDED: default policy = the above

Directory.Build.props                 # AMENDED: NuGet Audit enforced at restore (R4)

docs/
├── adr/ADR-022-application-identities-as-tenant-members.md   # NEW, Accepted
└── operations/load-test-baseline.md                           # NEW: permanent SC-003 evidence
```

**Structure Decision**: Pipeline definitions live where GitHub requires them (`.github/workflows/`).
Anything with a lifecycle different from the S6 environment gets its own Terraform root: federated
identities and the app role (`persistent/`) must survive `terraform destroy`, and repository
configuration (`github/`) has nothing to do with Azure at all. The load test lives under `tests/`
because it is a test, even though only the pipeline runs it.

## Phase 0 — Prerequisites and branch base

**This branch must be based on `005-terraform-azure`.** **S6 is now on `main`** (merged 2026-10-16, Container Apps per ADR-023), so this branch is rebased onto `main`. The pipeline updates S6's container app, pushes to S6's ACR, and three amendments land in S6's Terraform.

Execution also depends on decisions outside this plan:
1. ~~ADR-022 accepted~~ — **done 2026-09-29**.
2. **S6 applied to a funded subscription** (blocks every task that runs against Azure). As with S6, all file-authoring tasks can be completed first and verified later in one combined Azure session.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Two new Terraform roots (`persistent/`, `github/`) | Different lifecycles from the destroyable S6 environment | Putting identities in the S6 root changes their client IDs on every rebuild; repository config has no business in an Azure state file |
| An application-code change in a CI/CD slice | The load test cannot authenticate unattended without a stored credential otherwise | Every credential-free alternative either bypasses the path under test or plants a backdoor (research R7) |
| A second workflow (`gate-selftest.yml`) | SC-002 requires re-verification whenever a gate changes | A one-time manual demo proves the gate worked once, not that it still works |

## Phases

### Phase 1 — Gates on pull requests (US2, most of US1)

1. `validate-commit-messages.sh` (R5) and its `commit-messages` job.
2. `secret-scan` job: gitleaks over the commit range (R3).
3. NuGet Audit in `Directory.Build.props` (R4); resolve any finding it surfaces on the current dependency set.
4. `build-test` job: restore (audit), build, unit tests, architecture tests; `integration-test` job in parallel.
5. `container-scan` job: build the image once, run the S5 vulnerability and secret scan scripts.
6. `gate-selftest.yml` with the four negative proofs (R11).
7. Per-job summaries so a failure is identifiable in under two minutes (SC-005): stage table, first error surfaced as an annotation.

### Phase 2 — Protection as code (US3, FR-011)

1. `infrastructure/github/`: ruleset on `main` (required checks = Phase 1 job names, no bypass actors), environments `dev` and `production` (required reviewer, `can_admins_bypass = false`), repository variables.
2. `production` job in `pipeline.yml`: approval-expiry check (R12), then print the would-deploy record. No deploy.

### Phase 3 — Publish and deploy (US1 end-to-end)

1. `infrastructure/terraform/persistent/`: `id-github-deployer` + federated credential.
2. S6 amendments: `ignore_changes` on the container image and `deploy.sh`/`rollback.sh` switching to `az containerapp update` after first create (R2, R10), APIM all-method operations, deployer role assignments in the S6 root.
3. `container-publish` job (main only): supersession guard (R9), push the scanned image by commit SHA.
4. `deploy-dev` job: guard, preflight (R10), `az containerapp update` with a revision health poll, `dev-deploy` concurrency group.

### Phase 4 — Performance verification (US4)

1. `CallerAuthorizationPolicy` + `Program.cs` default policy; unit tests (each accepted/rejected token shape) and integration tests (automation identity refused cross-tenant).
2. `persistent/app-role.tf`: app role on the API registration, assignment to `id-loadtest-client`.
3. `tests/load/seed.sh` + `tests/load/tenant-reads.js` (R8).
4. `load-test` job: guard, token via OIDC, seed, run k6, archive the summary, fail on threshold breach.
5. Record the measured result in `docs/operations/load-test-baseline.md`; mark spec 001 SC-003 verified.

### Phase 5 — Verification and closure

1. Ten consecutive real runs on `main` timed against the 20-minute budget (SC-001).
2. All four negative proofs observed failing in the pipeline itself, not only in the self-test (SC-002).
3. An approval granted, an approval denied, and an admin-bypass attempt refused (SC-003).
4. Roadmap S7 *Done when* updated from evidence; `CLAUDE.md`'s CI claim now true.

## Global Constraints

- **Zero repository secrets.** If a step seems to need one, the design is wrong — use OIDC or a non-sensitive variable.
- **Build once, deploy what was scanned.** No image is rebuilt after its scans pass.
- **Never cancel mid-deploy.** Supersession happens only at job boundaries (R9).
- **The production stage performs no deployment** in this slice — it proves the gate, nothing more.
- **Existing tests keep passing**, and the pipeline runs exactly the suites a developer runs locally.
- **No gate may be weakened to make the pipeline green.** A failing gate on existing code is a finding to fix (e.g., an upgraded dependency), never a threshold to relax.
