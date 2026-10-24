# Feature Specification: CI/CD Pipeline with Performance Verification

> **Historical — multi-tenancy was removed on 2026-10-23** ([ADR-025](../../docs/adr/ADR-025-single-organization.md)). This spec describes the system as built at the time and is not rewritten. Where it says tenant, the current code has one organization per deployment, and the service is `src/Identity`. The load test reads `GET /me` with 50 callers instead of seeding 20 tenants.

**Feature Branch**: `006-ci-cd`  
**Created**: 2026-09-27  
**Status**: Draft  
**Input**: User description: "start S7 nhé"

## Clarifications

### Session 2026-09-27

- Q: US3 says production is gated by human approval, but production doesn't exist in Horizon 1 — what concretely is the "placeholder post-dev environment" that FR-009/FR-010's acceptance tests trigger against? → A: A no-op "would-deploy-to-production" stage — no real environment, no real deploy; just prints the change, requires approval, records the approver. The gate mechanism is fully tested; the "deploy" itself is a stub.
- Q: FR-014 says concurrent pipeline runs must "serialize" — does that mean strict queueing in commit order, or preempt-latest (cancel earlier in-flight for the newer commit)? → A: Preempt-latest — when a newer commit arrives, in-flight pipelines for older commits are cancelled at the next safe checkpoint, and only the latest wins.
- Q: FR-013 says the load-test stage fails when the error rate exceeds "a documented threshold" — what is that threshold? → A: 1% — tolerates ~1 error per 100 requests, matching a standard SLO "three nines" bar; catches real regressions (usually 5%+) while tolerating transient cloud blips.
- Q: Edge case #5 says pending approvals expire with a documented timeout — what is that timeout? → A: 7 days — covers weekends + reasonable PTO; the underlying scan artifacts (secret/dep/image) approximately expire in this window anyway, so a deploy still pending after a week should restart with fresh scans regardless.
- Q: Where does load-test load come from — GitHub-hosted runner, self-hosted in the compute platform, or Azure Load Testing service? → A: GitHub-hosted runner (`ubuntu-latest`), which runs in an Azure region matching dev's default — no extra infra to provision, near-representative latency for a research project.

## User Scenarios & Testing

### User Story 1 — Commit-to-Dev Automation (Priority: P1)

A developer pushes a commit to the main branch (or opens a pull request), and the pipeline runs the full sequence — build, unit tests, integration tests, architecture tests, secret scan, dependency vulnerability scan, container build, container image scan, ACR push, and container app update in dev — with no manual step, completing in under 20 minutes. The developer can watch the pipeline progress in real time and, when it finishes green, exercise their change on the dev environment immediately.

**Why this priority**: This is the core value proposition of the slice. Without a working unattended path from commit to dev, none of the other stories (safety gates, load testing) matter — they're checks on a pipeline that has to exist first. This story delivers the roadmap's headline "Done when" ("Commit → dev in under 20 minutes, fully unattended").

**Independent Test**: Push a trivial, valid change (e.g., a docstring update) to the main branch and observe the pipeline execute every stage without human intervention and complete in under 20 minutes, with the change verifiably live in dev (verified by hitting the health endpoint and observing the change reflected).

**Acceptance Scenarios**:

1. **Given** a valid commit is pushed to the main branch, **When** the pipeline runs, **Then** every stage (build → unit → integration → architecture → secret scan → dependency scan → container build → image scan → push ACR → deploy dev) executes automatically without human input and the change is live in dev in under 20 minutes.
2. **Given** the pipeline is running, **When** a developer views the pipeline UI, **Then** each stage's status (queued/running/passed/failed) is visible with per-stage timing and logs accessible for troubleshooting.
3. **Given** a stage fails, **When** the developer inspects the pipeline output, **Then** the failure reason is clearly reported at the top of the stage log (not buried in noise), the pipeline stops immediately (no further stages run), and the dev environment is left in its prior working state.

---

### User Story 2 — Bad Changes Are Rejected Before Reaching Dev (Priority: P2)

The pipeline detects and refuses to deploy any change that violates a foundational safety rule: an architectural-boundary violation, a committed secret, a dependency with a known high or critical vulnerability, or a commit message that doesn't follow the conventional-commits format. Each rejection produces a clear failure message identifying which rule fired and where.

**Why this priority**: This story is the "negative proof" that the pipeline is actually enforcing quality, not merely running. Constitution Principle VII ("Automated gates, not reviewer vigilance") is the philosophical foundation of the whole project — this story is where it becomes observable in behavior, not just claimed in documentation.

**Independent Test**: For each of the four rejection categories, deliberately introduce a violating change on a throwaway branch and verify the pipeline fails at the correct stage with a message naming the specific rule violated. Restore the change and verify the pipeline passes again.

**Acceptance Scenarios**:

1. **Given** a change is pushed that references a forbidden dependency direction (e.g., a domain-layer file importing from the infrastructure layer), **When** the pipeline runs, **Then** the architecture-test stage fails and names the specific rule and file(s) involved.
2. **Given** a change contains a plausible-looking test secret (e.g., an AWS access key pattern) in any file, **When** the pipeline runs, **Then** the secret-scan stage fails and names the file and line — regardless of whether the secret is real, deliberately-planted, or accidentally introduced.
3. **Given** a project dependency is updated to a version with a known high- or critical-severity CVE, **When** the pipeline runs, **Then** the dependency-scan stage fails and names the package, version, and CVE identifier.
4. **Given** a commit is pushed with a message that doesn't follow the conventional-commits format (e.g., "fixed stuff"), **When** the pipeline runs, **Then** the commit-validation stage fails and returns a message explaining the expected format.
5. **Given** any of the above rejections occurs, **When** the pipeline stops, **Then** the change is not merged, the dev environment is not touched, and no partial artifact is left in ACR.

---

### User Story 3 — Production is Gated by Explicit Human Approval (Priority: P3)

Deploying to any environment beyond dev requires an explicit human approval step in the pipeline — the pipeline cannot self-approve, and no automation path exists that bypasses this. The approver's identity is recorded with the deployment.

**Why this priority**: Constitution Principle I ("Human Authority Over Intent, Architecture, and Risk") makes this non-negotiable, and Constitution Quality Gates row 11 lists "Human approval required for production deployment." Even though production doesn't yet exist in this slice (Horizon 1 is dev-only), the *gate mechanism* has to exist and be provably tested before it can protect a real production environment.

**Independent Test**: Attempt to trigger the no-op "would-deploy-to-production" stage (a stub that prints the change and requires approval but performs no real deploy — clarified 2026-09-27) and confirm the pipeline pauses, waits for approval, records the approver's identity when granted, and refuses to proceed when denied.

**Acceptance Scenarios**:

1. **Given** the pipeline has successfully deployed to dev, **When** a deploy to a post-dev environment is triggered, **Then** the pipeline pauses at a manual approval step naming the change's author, commit SHA, and target environment.
2. **Given** the approval step is pending, **When** an authorized approver grants approval, **Then** the deploy proceeds and the approver's identity is recorded on the deployment record.
3. **Given** the approval step is pending, **When** an authorized approver denies approval (or approval times out), **Then** the deploy does not proceed and the change is not deployed anywhere beyond dev.
4. **Given** no automation path or configuration setting can be used to bypass the approval gate, **When** verified by attempting to trigger a post-dev deploy without going through the approval step (via any documented pipeline mechanism), **Then** the attempt fails.

---

### User Story 4 — Performance Verification Against a Real Environment (Priority: P4)

The pipeline runs a load test against the deployed dev environment as one of its stages, verifying spec 001's SC-003 (95% of tenant reads complete in under 1 second at 50 concurrent users across 20 tenants) — the first time this criterion is measurable, because it requires both a pipeline to run the test and a real deployed environment to run it against.

**Why this priority**: Roadmap S7's "Done when" explicitly requires "Spec 001 SC-003 verified" here, and traceability.md U6 documents that this verification was deliberately deferred to S7 for exactly this reason. Priority 4 because the pipeline structure (P1) and the safety gates (P2, P3) are more foundational — a load test is meaningful only if the pipeline that runs it is itself sound.

**Independent Test**: After US1's pipeline is running and deploys a known-good build to dev, trigger the load-test stage against that deployed environment and verify the report shows the p95 latency for tenant reads at 50 concurrent users across 20 tenants, with the pipeline pass/fail decision matching whether that p95 is under 1 second.

**Acceptance Scenarios**:

1. **Given** a healthy application is deployed in dev, **When** the load-test stage runs, **Then** it exercises tenant-read operations at 50 concurrent users across 20 tenants and records p50/p95/p99 latency plus error rate.
2. **Given** the load test completes, **When** the p95 latency is under 1 second, **Then** the stage passes and the measurement is recorded as verification of spec 001 SC-003.
3. **Given** the load test completes, **When** the p95 latency is at or above 1 second (or the error rate exceeds a documented threshold), **Then** the stage fails, the failure names the offending metric, and the deploy that preceded it remains in dev while the pipeline is marked failed for that run.

---

### Edge Cases

- What happens when the pipeline is triggered by two commits arriving in quick succession? The older commit's pipeline is cancelled at the next safe checkpoint (never mid-deploy) and only the latest wins (FR-014, preempt-latest — clarified 2026-09-27). Developers can observe this in the pipeline UI as an explicit "cancelled — superseded by <newer commit>" outcome, not silent disappearance.
- What happens when a pipeline run is manually cancelled mid-deploy? The dev environment must not be left in a broken half-deployed state — either the previous version continues serving (rollback semantics from spec 005 FR-013/FR-014) or the failed deploy is rolled back automatically.
- What happens when the load-test stage is flaky (e.g., a transient Azure networking blip causes a spurious slow request)? The documented policy (contracts/load-test.md) is zero automatic retries: a breach fails the run and a re-run is a deliberate manual action — never a silent retry that hides real regressions.
- What happens when a secret is committed and merged before the scan catches it (retroactively discovered)? The pipeline can't undo the leak, but must at least catch it on the *next* run and fail loudly enough that the operator knows to rotate the leaked secret.
- What happens when the pipeline succeeds but an approval-gated post-dev deploy is left pending indefinitely? The pending approval expires after 7 days (clarified 2026-09-27), matching the natural expiry window of the underlying scan artifacts (secret/dep/image) — a deploy still pending after a week must restart the pipeline to get fresh scans, rather than being auto-approved against stale evidence.
- What happens when a pipeline-triggered `az containerapp update` runs against a dev environment that is temporarily unreachable (e.g., someone ran `terraform destroy` per the S6 cost-control discipline)? The pipeline must fail cleanly with a message identifying the missing environment, not hang or leave the pipeline in an ambiguous state.

## Requirements

### Functional Requirements

- **FR-001**: The pipeline MUST execute the full stage sequence (build → unit → integration → architecture → secret scan → dependency scan → container build → image scan → push ACR → deploy dev → load test) on every push to the main branch. Every pull request targeting main runs the gate stages (commit validation through image scan) only; publish, deploy, load test and the post-dev stub run only after merge.
- **FR-002**: The full pipeline run from push to dev deployment MUST complete in under 20 minutes for a typical change.
- **FR-003**: The pipeline MUST execute every stage without manual intervention between stages — a green pipeline reaches dev automatically.
- **FR-004**: The architecture-test stage MUST fail the pipeline when any of the S3 architecture-test suites report a rule violation, naming the rule and offending file(s).
- **FR-005**: The secret-scan stage MUST fail the pipeline when any credential-pattern match is found in the diff or the built container image, regardless of whether the match is deliberately planted, accidental, or a real leak.
- **FR-006**: The dependency-scan stage MUST fail the pipeline when any project dependency is at a version with a known high- or critical-severity CVE.
- **FR-007**: The commit-validation stage MUST fail the pipeline when a commit message on the branch under test does not follow the Conventional Commits format.
- **FR-008**: The container-image-scan stage MUST fail the pipeline when the built container image contains a high- or critical-severity vulnerability (existing S5 Trivy scans, invoked from the pipeline rather than a developer's laptop).
- **FR-009**: Deploying to any environment beyond dev MUST require an explicit human approval step within the pipeline — no configuration path may bypass this. In this slice, "post-dev deploy" is a no-op stub stage that prints the change and requires approval but performs no real deploy (production infrastructure does not exist in Horizon 1); the gate mechanism itself is fully wired and tested, so a future real production environment can slot in behind the same approval flow.
- **FR-010**: The approval step MUST record the approver's identity, the change being approved, and the timestamp on the deployment record.
- **FR-011**: The main branch MUST be protected such that direct pushes without a passing pipeline are refused by the Git host (branch protection is enforced by the platform, not merely documented).
- **FR-012**: The load-test stage MUST exercise spec 001's SC-003 scenario (50 concurrent users across 20 tenants performing tenant reads) against the deployed dev environment and report p50/p95/p99 latency plus error rate.
- **FR-013**: The load-test stage MUST fail the pipeline when p95 latency exceeds 1 second (spec 001 SC-003) OR when the error rate exceeds 1% (clarified 2026-09-27) — standard SLO "three nines" bar, aggressive enough to catch real regressions (which typically show up as 5%+ under load) while tolerating occasional transient cloud blips.
- **FR-014**: Concurrent pipeline runs for different commits MUST preempt-latest (clarified 2026-09-27): when a newer commit arrives on the main branch, any in-flight pipeline for an older commit is cancelled at the next safe checkpoint (never mid-deploy), and only the latest commit's pipeline continues. A slower earlier run can never overwrite a faster later run because the earlier run is cancelled before it reaches its deploy stage.
- **FR-015**: A cancelled or failed deploy stage MUST NOT leave dev in a partially-deployed state — either the previous version continues serving (relying on spec 005 FR-014's single-revision guarantee: a revision that never passes its probes takes no traffic) or the pipeline redeploys the previous image tag.
- **FR-016**: Pipeline definitions, secrets/variables, and workflow files MUST themselves be code — no pipeline configuration created only by clicking in the CI/CD platform's UI.

### Key Entities

- **Pipeline Run**: A single execution of the pipeline for one commit, with a stable identifier, a sequence of stage results, timing information, and (for post-dev deploys) an approval record.
- **Stage**: One step in the pipeline sequence (build, test, scan, deploy, load-test) with its own pass/fail outcome, logs, and duration.
- **Approval Record**: The audit trail for a post-dev deploy — approver identity, commit SHA, target environment, granted-or-denied outcome, timestamp.
- **Load-Test Result**: The measurement output of the load-test stage — p50/p95/p99 latency, error rate, concurrent-user count, tenant count, sample size — recorded as verification evidence for spec 001 SC-003.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A valid commit to main reaches the dev environment in under 20 minutes of wall-clock time on at least 19 of 20 consecutive real runs (95%).
- **SC-002**: Every one of the four "negative proof" scenarios (architecture violation, planted secret, vulnerable dependency, non-conforming commit message) is caught by the pipeline and rejected before dev deployment — verified once per category, then re-verified whenever the corresponding gate changes.
- **SC-003**: Zero deployments to any environment beyond dev occur without a recorded human approval — verified by inspecting the deployment records over the slice's lifetime.
- **SC-004**: Spec 001 SC-003 is verified: 95% of tenant-read requests at 50 concurrent users across 20 tenants complete in under 1 second, measured against the deployed dev environment.
- **SC-005**: A developer new to the project can identify which stage failed and why from the pipeline UI in under 2 minutes on a random pipeline failure, without asking another team member.
- **SC-006**: Pipeline configuration is fully reproducible from Git — a fresh clone of the repository plus a fresh Git-host account can produce an identical pipeline setup with no undocumented manual steps.

## Assumptions

- The dev environment provisioned by spec 005 (S6) is standing when the pipeline attempts to deploy — the pipeline does not itself provision infrastructure; it deploys to infrastructure that already exists. If S6's manual cost-control discipline has torn the environment down, pipeline runs will fail at the deploy stage with a clear message (edge case above), which is expected behavior, not a defect.
- Secret and dependency scanning use the same underlying tools already introduced in earlier slices where applicable (Trivy for container image scanning from S5), invoked from the pipeline rather than a developer's laptop.
- The load-test tool produces machine-readable output (JSON or similar) so the pipeline can parse pass/fail decisions from measured metrics — the specific tool choice is a plan-phase decision.
- The Git host (GitHub, per CLAUDE.md's `gh` command references) provides branch protection, environments with approval gates, and workflow-as-code — these are baseline features, not custom-built for this slice.
- Only the `main` branch is protected in this slice; feature branches remain freely pushable so speckit's branch-per-feature workflow continues to work.
- Load-test load is generated from the GitHub-hosted runner (`ubuntu-latest`, clarified 2026-09-27), which runs in Azure infrastructure matching the dev environment's region — this gives near-representative latency numbers without provisioning additional load-generation infrastructure. If the SC-004 measurement ever proves untrustworthy due to cross-region variance, upgrading to a self-hosted runner inside the dev Container Apps environment is the documented next step, but is deferred until measurement problems surface.

## Scope Boundaries

**In scope**: Everything listed under "Build" in roadmap S7 — the full pipeline sequence, conventional-commit validation, branch protection, the human-approval gate before post-dev deploys, and the load test verifying spec 001 SC-003 against the deployed dev environment.

**Out of scope**:
- A production environment or the resources it would need (deferred to post-Gate-1; ADR-007)
- Blue/green deployment (roadmap S7 "Not")
- AI evaluation in the pipeline (deferred to S15)
- QA environment (deferred to post-Gate-1 per traceability.md U7)
- Security testing beyond secret + dependency + image scanning (deferred; traceability.md U6 notes secret/dep scanning is not security *testing*)
- End-to-end testing (currently unscheduled per traceability.md U6 — recommend S7 also owns E2E, but the roadmap's "Build" list doesn't include it; adding it here would expand scope beyond the roadmap without discussion)

## Dependencies

- **S3 (Architecture Tests)**: The gates FR-004 depends on
- **S5 (Containerization)**: The Trivy scan scripts FR-005/FR-008 invoke; the Dockerfile the container-build stage builds
- **S6 (Terraform → Azure)**: The dev environment the deploy stage deploys into; the ACR the push stage pushes into; the container app whose image the deploy stage updates
- **Spec 001 (Auth + Tenant)**: The SC-003 criterion FR-013 verifies
- **ADR-022**: application identities as tenant members — the load test's credential-free authentication
- **ADR-007** and **ADR-023**: full architecture in Horizon 1, on Azure Container Apps (ADR-023, 2026-10-16) — the topology the load test measures against
- **Constitution Principle I** (Human Authority) — FR-009's foundation
- **Constitution Principle VII** (Automated Gates) — the whole slice's philosophical foundation

## Deferred Requirements

None inherited into this slice. Spec 001 SC-003 was deferred *to* this slice (traceability.md U6) and is verified here via FR-012/FR-013/SC-004.
