# Pipeline Contract

**Branch**: `006-ci-cd` | **Date**: 2026-09-29

The job names below are a contract: the `main` ruleset lists them as required status checks
(`contracts/github-config.md`). Renaming a job without updating the ruleset silently removes a gate.

## Triggers

| Event | Jobs that run |
|---|---|
| `pull_request` → `main` | all **gate** jobs |
| `push` → `main` | all gate jobs + `container-publish` → `deploy-dev` → `load-test` → `production` |
| `workflow_dispatch` | same as `push` (manual re-run with fresh scans, e.g. after approval expiry) |

## Jobs

### Gate jobs (PR and main)

| Job | Depends on | Does | Fails when |
|---|---|---|---|
| `commit-messages` | — | `validate-commit-messages.sh <base> <head>` | any non-merge commit breaks the grammar (`commit-message.md`) |
| `secret-scan` | — | gitleaks over the commit range | any finding |
| `build-test` | — | restore (NuGet Audit), build, unit tests, architecture tests | restore advisory ≥ high (NU1903/NU1904); any build error; any test failure |
| `integration-test` | — | integration tests (Testcontainers SQL Server) | any test failure |
| `container-scan` | — | `docker build` once; `scan-image-vulnerabilities.sh`; `scan-image-secrets.sh`; save image as artifact | any HIGH/CRITICAL CVE; any secret; bait image **not** detected |

### Delivery jobs (main only)

| Job | Depends on | Environment | Does |
|---|---|---|---|
| `container-publish` | all gate jobs | `dev` | supersession guard; OIDC login as `id-github-deployer`; load the scanned image artifact; push `<acr>/tenancy-api:<sha>` |
| `deploy-dev` | `container-publish` | `dev` | guard; preflight (`az containerapp show`); `az containerapp update --image <acr>/tenancy-api:<sha>`; poll the new revision until healthy (5 min timeout), fail the job if it is not. The previous revision keeps serving throughout |
| `load-test` | `deploy-dev` | `dev` | guard; OIDC login as `id-loadtest-client`; token for the API audience; `seed.sh`; k6 (`load-test.md`) |
| `production` | `load-test` | `production` (required reviewer) | approval-expiry check (7 days); write the would-deploy record. **No deployment.** |

## Concurrency

- `deploy-dev`: `concurrency: { group: dev-deploy, cancel-in-progress: false }` — two deploys never overlap and a running deploy is never interrupted.
- Supersession (R9): the guard at the start of every delivery job compares `github.sha` to the tip of `origin/main`; if newer, it writes `Superseded by <sha>` to the summary and runs `gh run cancel $GITHUB_RUN_ID`.
- No workflow-level `cancel-in-progress` — it would cancel mid-deploy.

## Permissions

Workflow default: `contents: read` and `actions: read` (the job summary looks up the first failed step). Raised per job only where needed:

| Job | Extra permissions |
|---|---|
| delivery jobs | `id-token: write` (OIDC), `actions: write` (self-cancel on supersession) |
| `production` | `deployments: write` is implicit to environments; nothing else |

## Inputs (repository variables — never secrets)

`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_DEPLOYER_CLIENT_ID`, `AZURE_LOADTEST_CLIENT_ID`,
`TENANCY_API_APP_ID_URI`, `ACR_LOGIN_SERVER`, `RESOURCE_GROUP`, `CONTAINER_APP_NAME`,
`FRONTDOOR_ENDPOINT`. All are identifiers or hostnames; none grants access on its own.

## Failure semantics

- Any failed job stops everything downstream (`needs:`); dev is untouched unless `deploy-dev` itself ran.
- A failed or interrupted `deploy-dev` leaves the previous release serving (single revision mode, spec 005 FR-014).
- A missing dev environment fails `deploy-dev` at preflight with: *"Dev environment not found — it may have been destroyed per S6 cost discipline. Apply it with specs/005-terraform-azure/quickstart.md, then re-run."*
- Every job writes a one-line outcome to `$GITHUB_STEP_SUMMARY`, and the first error of a failed step is emitted as an `::error::` annotation, so the failure is visible on the run page without opening logs (SC-005).

## Duration budget

Critical path ≈ 14 minutes against the 20-minute SC-001 limit (research R13).
