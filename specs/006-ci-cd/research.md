# Research: CI/CD Pipeline with Performance Verification

**Branch**: `006-ci-cd` | **Date**: 2026-09-29

Each decision records what was chosen, why, and what was rejected. Decisions marked
**⚠ needs human acceptance** change the platform's security surface and are drafted, not
settled, until the project owner accepts them (Constitution Principle I and II).

## Facts established before deciding

These were verified against the repository, not assumed:

- **No CI exists today.** There is no `.github/` directory. `CLAUDE.md` states that "CI
  validates [Conventional Commits] on every push" — that claim is currently false. This slice
  makes it true.
- **Existing history contains non-conforming merge commits** (`Merge branch
  '004-containerization'`, `Merge pull request #4 ...`). Any commit-message gate must decide what
  to do about merge commits, or it fails on the repository's own history.
- **Integration tests need Docker.** `tests/Tenancy.IntegrationTests` uses
  `Testcontainers.MsSql` 4.11.0 with SQL Server 2022. GitHub-hosted `ubuntu-latest` runners ship a
  Docker daemon, so this works unmodified.
- **The API authenticates Entra bearer tokens but enforces no scope.** `Program.cs` wires
  `AddMicrosoftIdentityWebApi` and nothing checks `scp`/`roles`. Microsoft.Identity.Web itself
  rejects a token carrying *neither* claim, so today the API is safe only because its app
  registration defines no app roles — no application can obtain a token with a `roles` claim. That
  is safety by accident, not by policy. See R7.
- **Callers are identified by `oid` and provisioned just-in-time.** `JitProvisionCallerFilter`
  resolves `tid` + `oid` and falls back to `{oid}@unresolved.invalid` when no email-like claim is
  present — so a non-human identity can already be provisioned without code changes.
- **Two S6 gaps block this slice** (both on branch `005-terraform-azure`):
  1. APIM's API definition has a single `GET /*` operation. Load-test seeding needs `POST
     /tenants`, which APIM would reject with 404.
  2. The AKS cluster has no Entra ID integration (`azure_active_directory_role_based_access_control`
     absent), so a pipeline identity has no way to authenticate to the Kubernetes API without a
     static admin kubeconfig — a stored credential.

## R1 — CI/CD platform

**Decision**: GitHub Actions, with every workflow in `.github/workflows/`.

**Rationale**: The repository is hosted on GitHub; spec Assumptions already name it. Actions
provides the three platform features the spec needs as built-ins — workflow-as-code (FR-016),
environments with required reviewers (FR-009/FR-010), and repository rulesets (FR-011) — plus
native OIDC federation to Entra ID (R2), which is what makes a zero-secret pipeline possible.

**Alternatives considered**:
- *Azure DevOps Pipelines*: Azure-native (ADR-001), but the code lives on GitHub; running a second
  platform to mirror it adds a sync problem for no capability gain.
- *Self-hosted runner platform (Jenkins, etc.)*: More infrastructure to run and destroy, directly
  against the S6 cost discipline.

## R2 — Pipeline authentication to Azure: OIDC federation, zero stored secrets

**Decision**: GitHub Actions obtains Azure tokens through **workload identity federation**
(`azure/login` with `client-id` + `tenant-id` + `subscription-id`, `permissions: id-token: write`).
The federated identities are **user-assigned managed identities** living in a new, persistent
Terraform root (`infrastructure/terraform/persistent/`), not in the destroyable S6 environment.

Two identities, least privilege:

| Identity | Federated subject | Granted |
|---|---|---|
| `id-github-deployer` | `repo:ducnguyenhuu/delivery-intelligent-platform:environment:dev` | `AcrPush` on ACR; `Azure Kubernetes Service Cluster User Role` + `Azure Kubernetes Service RBAC Writer` scoped to the `default` namespace |
| `id-loadtest-client` | same subject | App role `Tenancy.Automation.Member` on the Tenancy API (R7); **no** Azure RBAC at all |

**Rationale**:
- Constitution Principle V: "Stored credentials, connection strings with secrets, and long-lived
  keys are prohibited." OIDC federation means the repository holds **zero secrets** — only
  non-sensitive identifiers stored as GitHub *variables*, not secrets.
- **Why persistent, not in the S6 root**: S6's cost discipline runs `terraform destroy` after every
  session. An identity created there would get a new client ID on every rebuild, forcing the
  GitHub variables to be re-edited every session. Managed identities cost nothing while idle. The
  identities persist; the *role assignments* are created by the S6 root against whatever ACR/AKS
  currently exists, and disappear with them.
- **Why two identities**: the deployer must never be a tenant member, and the load tester must never
  be able to deploy. One identity holding both would let a compromised load-test step push images.

**Alternatives considered**:
- *Service principal with a client secret in GitHub Secrets*: The textbook setup and a direct
  Principle V violation — a long-lived key that must be rotated and can leak.
- *Identities inside the S6 root*: Rejected for the client-ID churn described above.
- *App registrations instead of managed identities*: Both support federation; managed identities
  have no credential surface at all and need no application object.

**S6 amendment required**: the S6 AKS module must enable Entra ID integration with Azure RBAC
(`azure_active_directory_role_based_access_control { azure_rbac_enabled = true }`) and
`local_account_disabled = true`, so the deployer authenticates with its federated token through
`kubelogin` rather than a static kubeconfig.

## R3 — Secret scanning

**Decision**: Two layers.
1. **Source**: `gitleaks` against the pushed commits (PR: the PR's commit range; push to `main`:
   the pushed range; the self-test and a weekly scheduled run scan full history).
2. **Image**: the existing S5 `infrastructure/scripts/scan-image-secrets.sh` (Trivy filesystem +
   image-config scanners, with its bait-image negative proof), invoked from the pipeline instead of
   a laptop.

**Rationale**: FR-005 covers both "the diff" and "the built container image." gitleaks is the
de-facto source scanner, runs as a single static binary, and exits non-zero on a finding. S5
already built and proved the image scanner; reusing it is the whole point of having it.

**Alternatives considered**:
- *GitHub secret scanning / push protection*: Useful, but it is a repository setting with no
  pipeline failure signal and no way to prove it catches a planted secret on demand (SC-002).
- *Trivy's filesystem scanner for source too*: Workable, but gitleaks' commit-range mode is what
  catches a secret introduced *and removed* within the same PR — a secret that is gone from the
  final tree but still in history.

## R4 — Dependency vulnerability scanning

**Decision**: **NuGet Audit, enforced at restore**, set once in `Directory.Build.props`:

```xml
<NuGetAudit>true</NuGetAudit>
<NuGetAuditMode>all</NuGetAuditMode>        <!-- transitive packages too -->
<NuGetAuditLevel>high</NuGetAuditLevel>
<WarningsAsErrors>$(WarningsAsErrors);NU1903;NU1904</WarningsAsErrors>  <!-- high, critical -->
```

**Rationale**: The build itself fails on a high/critical advisory, so the gate is identical on a
developer's machine and in the pipeline — no separate tool, no output parsing, and nothing that
can be skipped by forgetting to run a step. `NuGetAuditMode=all` matters: most vulnerable packages
arrive transitively.

**Alternatives considered**:
- *`dotnet list package --vulnerable --include-transitive` in a pipeline step*: Same data source,
  but only enforced where the step runs, and the text output needs parsing to produce a pass/fail.
- *Dependabot alerts*: Notification, not a gate.
- *Trivy filesystem scan of `packages.lock.json`*: No lock files exist today; adding them is a
  larger change than this gate needs.

**Risk**: enabling this may fail the build on the *current* dependency set the first time it runs.
That is a finding, not a gate defect — it is resolved by upgrading, not by lowering the level.

## R5 — Commit-message validation

**Decision**: A dependency-free Bash script, `infrastructure/scripts/validate-commit-messages.sh
<base> <head>`, that checks every **non-merge** commit in the range (`git log --no-merges`)
against the Conventional Commits grammar with the allowed types from `CLAUDE.md` (`feat fix chore
docs style refactor perf test build ci`), an optional `(scope)`, an optional `!`, and a non-empty
description.

Merge commits are excluded: they are authored by Git or GitHub, not by the developer, and the
repository's history already contains merges that would otherwise fail every run.

**Rationale**: The rule is one regular expression. `commitlint` would bring a Node toolchain and a
config file into a .NET repository to evaluate it. A shell script is also trivially runnable as a
local `commit-msg` hook, so the same check can run before a commit is ever pushed.

**Alternatives considered**:
- *commitlint*: Rejected for the toolchain cost above.
- *Validate only the PR title and require squash merges*: Valid, but it silently changes the
  repository's merge strategy, which is a decision this slice has no mandate to make.

## R6 — Branch protection and environments as code

**Decision**: A separate Terraform root, `infrastructure/github/`, using the
`integrations/github` provider, managing:
- a **repository ruleset** on `main`: pull request required, required status checks (the pipeline
  job names in `contracts/pipeline.md`), no force-push, no deletion, **no bypass actors** (so an
  admin is subject to it too);
- **environment `dev`**: deployment restricted to the `main` branch;
- **environment `production`**: one required reviewer (the project owner), `can_admins_bypass =
  false`, deployment restricted to `main`;
- the non-secret **repository variables** from R2.

Applied by a human from a workstation with `GITHUB_TOKEN=$(gh auth token)` — not from the
pipeline, so the pipeline never holds credentials that could weaken its own protection.

**Rationale**: FR-011 requires protection "enforced by the platform, not merely documented", and
FR-016 requires configuration as code. ADR-012 says all infrastructure is Terraform — branch
protection is infrastructure the pipeline's guarantees depend on. It is free and persistent, so it
lives in its own root with its own state key, outside the S6 apply/destroy cycle.

**Alternatives considered**:
- *A `gh api` script applying ruleset JSON*: Simpler, but a second IaC style and no drift detection.
- *Clicking in repository settings*: The exact failure FR-016 exists to prevent.

**Solo-project note on self-approval**: with a single human, the required reviewer on
`production` is also the commit author, so GitHub's `prevent_self_review` must stay off or nobody
could ever approve. FR-009's guarantee is that **no automation** can approve — a human must act —
not that approver and author differ. Four-eyes review is recorded as a *Revisit When* for the day
a second human joins.

## R7 — Load-test identity → ADR-022 (accepted 2026-09-29)

**Problem**: Spec 001 SC-003 must be measured against the deployed environment, through real
authentication, from an unattended pipeline. Every tenant endpoint requires an Entra bearer token.
There is no way to obtain a **delegated user** token without a human present except the resource
owner password flow, which needs a password stored as a secret and fails the moment the account is
subject to MFA.

**Decision**: Allow **application identities to be tenant members**, explicitly:
1. Add an app role `Tenancy.Automation.Member` (allowed member type: *Application*) to the Tenancy
   API registration, and assign it only to `id-loadtest-client` in dev.
2. Replace the API's implicit "any token with `scp` or `roles`" acceptance with an **explicit
   authorization policy**: a request is authorized only if its token carries the delegated scope
   `access_as_user` **or** the app role `Tenancy.Automation.Member`. Anything else is rejected.
3. Nothing else changes. The application identity is JIT-provisioned from `tid` + `oid` like any
   user, and it can see only tenants it is a member of — it becomes a member by creating them.
   Tenant isolation (Principle IV) applies to it unchanged, and gets its own cross-tenant tests.

**Rationale**:
- It is the only unattended option that stores no credential (the token comes from R2's OIDC).
- It **closes a latent gap** rather than opening one: today, adding any app role to the API
  registration for any reason would silently admit that app as a user. After this change, only the
  one named role is admitted.
- It adds no bypass: the automation identity has exactly a member's powers in exactly the tenants it
  belongs to — no cross-tenant or platform-wide access.

**Alternatives considered**:
- *Resource owner password flow with dedicated test users*: A stored password (Principle V) that
  breaks under MFA. Rejected.
- *Long-lived refresh tokens captured once and stored in GitHub Secrets*: A stored, revocable,
  90-day credential. Rejected for the same reason.
- *A test-only authentication scheme enabled in the deployed dev build*: A backdoor in a deployed
  artifact. Rejected outright.
- *Seed data and load from inside the cluster (a Kubernetes Job)*: Bypasses Front Door and APIM, so
  it would not measure the path spec 001 SC-003 is about, and still needs an identity.

**Documented limitation**: all 50 virtual users share **one** identity across 20 tenants. SC-003's
"50 concurrent users" is read as 50 concurrent sessions. Token validation is local (cached signing
keys) and membership lookup is per `(tenant, oid)`, so identity cardinality should not dominate
latency — but this is an assumption the result depends on, and it is stated as such in the
load-test report.

## R8 — Load-test tool

**Decision**: **k6**, run from the GitHub-hosted runner (clarified 2026-09-27), with thresholds as
the pass/fail mechanism:

```js
thresholds: {
  'http_req_duration{phase:steady,kind:tenant-read}': ['p(95)<1000'],  // spec 001 SC-003
  'http_req_failed{phase:steady}': ['rate<0.01'],                      // FR-013, 1%
}
```

k6 exits non-zero when a threshold is breached, and `--summary-export` writes the machine-readable
result the pipeline archives and summarizes.

**Rationale**: Thresholds are declarative and live beside the scenario, so the gate *is* the test
file. k6 is a single binary with an official Action, and its `scenarios` model expresses a warm-up
phase excluded from the measurement (JIT, connection pools, APIM cache) — without which the first
seconds would make p95 meaningless.

**Alternatives considered**:
- *NBomber*: .NET-native, but commercial licensing applies to organizational use.
- *JMeter*: XML test plans, heavier runtime, pass/fail needs a plugin or output parsing.
- *Azure Load Testing*: A paid managed service (rejected in clarification Q5).

## R9 — "Preempt-latest" without ever cancelling mid-deploy

**Problem**: FR-014 (clarified) wants older runs cancelled at a *safe checkpoint*, never during
`helm upgrade`. GitHub's workflow-level `concurrency: cancel-in-progress: true` cancels abruptly,
including mid-deploy. Job-level concurrency with `cancel-in-progress: false` keeps a deploy
running, but a queued *older* run can then deploy after a newer one finished — overwriting it.

**Decision**: A **supersession guard** step at the start of each expensive job on `main`
(`container-publish`, `deploy-dev`, `load-test`, `production`) compares `github.sha` with the
current tip of `origin/main`. If a newer commit exists, it prints `Superseded by <sha>` to the job
summary and cancels its own run (`gh run cancel $GITHUB_RUN_ID`, `permissions: actions: write`).
The deploy job additionally uses `concurrency: { group: dev-deploy, cancel-in-progress: false }` so
two deploys never overlap.

**Rationale**: Job boundaries *are* the safe checkpoints; nothing is interrupted mid-step. An older
run can never deploy after a newer commit exists, because it re-checks immediately before deploying.
And the cancellation shows up in the UI as an explicit cancelled run with a reason, matching the
clarified edge case.

## R10 — Deploy semantics and failure safety

**Decision**:
- The pipeline builds the image **once**, scans it, and pushes it tagged with the commit SHA. The
  deploy stage deploys that exact tag. Nothing is rebuilt after scanning.
- Deploy runs `helm upgrade --install --atomic --wait --timeout 5m` against the S6 chart. `--atomic`
  rolls a failed upgrade back automatically (FR-015).
- A pre-deploy step inspects the release; if it is stuck in `pending-*` (a previously cancelled
  runner), it issues `helm rollback` first.
- A **preflight** step checks the dev environment exists (`az aks show`). If S6's environment has
  been destroyed, the job fails immediately with an actionable message naming
  `specs/005-terraform-azure/quickstart.md`, instead of hanging on a DNS lookup.

S6's `infrastructure/scripts/deploy.sh` stays as the manual path; the pipeline does not call it,
because it rebuilds the image — the pipeline must deploy the artifact it scanned.

## R11 — Negative proofs are a standing test, not a one-time demo

**Decision**: A second workflow, `gate-selftest.yml`, runs on every pull request that touches a
gate definition, weekly on a schedule, and on demand. For each of the four rejection categories it
constructs a violating change in a scratch copy and asserts the gate **fails**:

| Gate | Planted violation | Expected |
|---|---|---|
| Architecture | A `Tenancy.Domain` source file referencing a `Tenancy.Infrastructure` type | Architecture tests fail, naming the rule and file |
| Secret | A generated synthetic key in a scratch file | gitleaks exits non-zero, naming file and line |
| Dependency | A canary project referencing a package version with a known high-severity advisory | Restore fails with NU1903/NU1904 |
| Commit message | A commit with message `fixed stuff` | Validator exits non-zero with the expected format |

**Rationale**: SC-002 says each category is "re-verified whenever the corresponding gate changes."
A gate that passes is indistinguishable from a gate that does nothing (the S5 bait-image lesson);
only a gate observed failing on a known violation is trusted. Running this on a schedule also
catches a gate silently weakened by a tool update.

## R12 — Approval expiry at 7 days

**Problem**: Clarified at 7 days, but GitHub fails a job waiting on environment review after 30
days, and that limit is not configurable.

**Decision**: The `production` job's first step compares the triggering commit's timestamp with the
current time. If more than 7 days have passed, it fails with `Approval expired — re-run the
pipeline for fresh scans`. An approval granted late therefore never deploys against stale scan
evidence, which is what the clarification protects.

## R13 — Pipeline duration budget (SC-001: under 20 minutes)

| Stage group | Runs | Estimate |
|---|---|---|
| Commit validation, secret scan | parallel | < 1 min |
| Build + unit + architecture (NuGet Audit at restore) | parallel | ~4 min |
| Integration tests (Testcontainers SQL Server) | parallel | ~5–6 min |
| Container build + vulnerability scan + secret scan (with bait) | parallel | ~4–5 min |
| Push to ACR | after all gates | ~1 min |
| Deploy dev (`--atomic --wait`) | after push | ~3 min |
| Load test (seed, 30 s warm-up, 2 min steady) | after deploy | ~3.5 min |
| **Critical path** | | **~14 min** |

Headroom of ~6 minutes. If measured runs exceed budget, the first lever is caching NuGet packages
and Docker layers; the second is pre-pulling the SQL Server image. Neither is built until a
measurement says it is needed.
