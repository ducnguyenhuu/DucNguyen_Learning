---

description: "Task list for Containerization (004-containerization)"
---

# Tasks: Containerization

**Input**: Design documents from `/specs/004-containerization/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: plan.md names exact test files for the foundational readiness change and the
tracked-configuration gate, so those are included. Other verification is the documented,
repeatable scripts and quickstart procedures this slice's Complexity Tracking calls out —
there is no CI yet (roadmap S7), so those steps are tasks to run and record, not automated
test files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 — maps to spec.md's priorities
- Paths are exact; this is a single project (`Tenancy`) at the repository root

---

## Phase 1: Setup

**Purpose**: Repository scaffolding the rest of the slice builds on

- [X] T001 [P] Create `.dockerignore` at repo root excluding `bin/`, `obj/`, `.git`, `.env`,
  `.env.*`, `**/appsettings.Development.json`, and user-secrets paths (contracts/container-image.md)
- [X] T002 [P] Create `.env.example` at repo root naming `MSSQL_SA_PASSWORD`,
  `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, `AZURE_AD_AUDIENCE`, `SAMPLE_RATE` with no
  values (contracts/compose-stack.md)
- [X] T003 [P] Scaffold `src/Tenancy/Tenancy.HealthProbe/Tenancy.HealthProbe.csproj` as a
  console project referencing only `HttpClient`, and add it to the solution

**Checkpoint**: Repo has the empty seams every later task fills in

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The draining readiness state, the probe, and the image itself — both P1 stories
depend on these existing before their own work can be verified

**⚠️ CRITICAL**: No user story task can be verified until this phase is complete

- [X] T004 [Tenancy.HealthProbe/Program.cs](../../src/Tenancy/Tenancy.HealthProbe/Program.cs)
  Implement the probe contract: `GET` the URL argument, 2 s timeout, exit 0 on 200, exit 1 on
  any other status/connection failure/timeout, one line to stderr on failure, no
  logging/config/telemetry dependency (contracts/container-image.md §Tenancy.HealthProbe contract)
- [X] T005 Extend `src/Tenancy/Tenancy.Api/HealthChecks/StartupState.cs` with a `Draining`
  state; encode the one-way transitions `Starting → Ready → Draining` and
  `Starting → Draining`, guarding against a late `MarkReady()` resurrecting readiness after
  `MarkStopping()` has been called (data-model.md §1)
- [X] T006 Extend `src/Tenancy/Tenancy.Api/HealthChecks/StartupHealthCheck.cs` so
  `/health/ready` reports `Draining` distinctly from both `Starting` and a dependency
  failure, with a human-distinguishable body for all three, while `/health/live` stays
  `Healthy` (depends on T005; data-model.md §1, contracts/container-image.md §Health)
- [X] T007 In `src/Tenancy/Tenancy.Api/Program.cs`, set
  `HostOptions.ShutdownTimeout = TimeSpan.FromSeconds(15)` explicitly and subscribe
  `IHostApplicationLifetime.ApplicationStopping` to call `MarkStopping()` (depends on T005;
  research.md R4)
- [X] T008 In `src/Tenancy/Tenancy.Api/Program.cs`, gate `app.UseHttpsRedirection()` on
  configuration so it is not called when no HTTPS port is discoverable inside a container
  (research.md R5)
- [X] T009 Write the root `Dockerfile`: SDK-stage restore/publish of `Tenancy.Api` and
  `Tenancy.HealthProbe` → `aspnet:10.0-noble-chiseled-extra` runtime stage, explicit
  `USER $APP_UID`, exec-form `ENTRYPOINT`, `InvariantGlobalization=true`,
  `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`, and an exec-form `HEALTHCHECK` invoking
  `Tenancy.HealthProbe` against `http://localhost:8080/health/ready` (depends on T004; plan.md
  §Project Structure, contracts/container-image.md)
- [X] T010 [P] Add `tests/Tenancy.UnitTests/Observability/StartupHealthCheckTests.cs (the draining cases were added there rather than in a new file)` proving
  `Starting`/`Ready`/`Draining` are three distinguishable results and that `MarkReady()`
  after `MarkStopping()` does not resurrect readiness (depends on T005, T006, T007)
- [X] T011 [P] Extend `tests/Tenancy.IntegrationTests/Observability/HealthCheckTests.cs` so
  `/health/ready` returns 503 with draining wording while `/health/live` stays 200 during
  shutdown (depends on T006)

**Checkpoint**: The image builds, has a working `HEALTHCHECK`, and readiness/shutdown
behaviour is proven at the unit/integration level — user story verification can begin

---

## Phase 3: User Story 1 - Start the complete local service stack (Priority: P1) 🎯 MVP

**Goal**: One documented command starts the service, its database, and the local collector,
and an authenticated tenant operation succeeds through it

**Independent Test**: `docker compose up --build --wait`, then complete an authenticated
tenant operation and confirm readiness and telemetry (spec.md US1)

- [X] T012 [US1] Create root `compose.yaml` with the `sqlserver` service (`platform:
  linux/amd64`, `MSSQL_SA_PASSWORD` from `.env`, named volume, `sqlcmd`-based healthcheck)
  and the `otel-collector` service (`extends` `deploy/otel-collector/docker-compose.yml`)
  (depends on T009; contracts/compose-stack.md §Services)
- [X] T013 [US1] Add the `api` service to `compose.yaml`: build from the root `Dockerfile`,
  `depends_on: sqlserver: condition: service_healthy`, port `8080:8080`, `read_only: true`
  with `tmpfs: [/tmp]`, `stop_grace_period: 45s`, and environment
  (`ConnectionStrings__TenancyDb` with `Encrypt=True;TrustServerCertificate=True`,
  `AzureAd__*`, `Observability__OtlpEndpoint=http://otel-collector:4317`,
  `ASPNETCORE_ENVIRONMENT=Development`), every required variable as `${VAR:?message}`
  (depends on T012; contracts/compose-stack.md §api, §Variable contract)
- [X] T014 [US1] Run quickstart.md §1: `cp .env.example .env`, fill in values,
  `docker compose up --build --wait`, confirm `/health/live` and `/health/ready` return 200,
  and complete a signed-in tenant operation with its trace visible in the collector's console
  output (depends on T013)
- [X] T015 [US1] Run quickstart.md §1's SC-001 timing: `docker compose down -v && time
  docker compose up --build --wait`, three consecutive times, confirm each reaches ready
  within 3 minutes (depends on T014)
- [X] T016 [US1] Run quickstart.md's missing-prerequisite path: unset
  `MSSQL_SA_PASSWORD`/rename `.env` and confirm `docker compose up` fails immediately naming
  the missing variable, with no default credential (depends on T013; FR-008 edge case 2)
- [X] T017 [US1] Run quickstart.md §2: stop `otel-collector`, confirm `/health/ready` stays
  200 and an authenticated tenant operation still succeeds; then repeat with the collector
  already stopped before `docker compose up` (depends on T014; FR-006, SC-005, edge case 4)

**Checkpoint**: User Story 1 is independently demonstrable — the stack starts, is usable, and
tolerates a collector outage

---

## Phase 4: User Story 2 - Run the service safely in a container (Priority: P1)

**Goal**: The running container is non-root, shuts down predictably, and the image carries no
secret — provably, including a scan proven able to fail

**Independent Test**: Inspect the running container's effective user, terminate it mid-request
and confirm a clean bounded exit, and run the secret scan against both the real and a baited
image (spec.md US2)

- [X] T018 [P] [US2] Create `tests/ArchitectureTests/ContainerConfigurationGates.cs`
  asserting no credential literal appears in any tracked container configuration file
  (`Dockerfile`, `compose.yaml`, `.env.example`) and that the `Dockerfile` sets a non-root
  `USER`; also assert no tracked container configuration file references an Azure
  credential, a Kubernetes/Helm manifest path, a registry push target, or pipeline logic
  (FR-011)
- [X] T019 [US2] Run quickstart.md §3: `docker inspect --format '{{.Config.User}}'` and
  `docker top` confirm uid 1654, never root; `docker inspect
  --format '{{.HostConfig.ReadonlyRootfs}}'` confirms `true` (depends on T013)
- [X] T020 [US2] Run quickstart.md §4: start a request, `docker compose stop api`, confirm
  the in-flight request drains, the exit code reflects a clean stop within the 45 s grace
  period, and the acknowledged mutation and its audit entry are both present afterward;
  during shutdown confirm `/health/ready` returns 503 with "shutting down" wording while
  `/health/live` stays 200. Repeat with `otel-collector` stopped beforehand to observe the
  OpenTelemetry flush-tail add to the drain and confirm the stop still completes within the
  45 s grace period (depends on T013, T011; research.md R4, spec.md edge case 4)
- [X] T021 [US2] Run quickstart.md's termination-before-readiness check: start then
  immediately stop the `api` service and confirm it exits cleanly having never returned 200
  from `/health/ready` (depends on T013; edge case 3)
- [X] T022 [P] [US2] Create `Dockerfile.secretbait` at repo root: copies a freshly generated
  throwaway RSA private key to `/app/config/leak.pem` and sets a synthetic
  `AWS_ACCESS_KEY_ID` `ENV` value, avoiding Trivy's `example`/`test` allow-list terms
  (research.md R6)
- [X] T023 [US2] Write `infrastructure/scripts/scan-image-secrets.sh`: runs
  `trivy image --scanners secret --image-config-scanners secret --severity HIGH,CRITICAL
  --exit-code 1` against the release-candidate image and fails on any finding; builds the
  bait image from `Dockerfile.secretbait` and fails if the scan finds **nothing** in it
  (depends on T022; FR-009)
- [X] T024 [US2] Run the scan script against `tenancy-api:rc`, and empirically verify the
  "not verified" whiteout question from research.md R6 with a two-stage bait (`COPY` a
  secret, then `RUN rm` it in a later layer) to record whether Trivy's secret scan catches a
  since-deleted secret (depends on T023)
- [X] T025 [US2] Write `infrastructure/scripts/scan-image-vulnerabilities.sh`: runs
  `trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1` against the
  release-candidate image at a fixed threshold, exit 1 on any unresolved finding (depends on
  T009; FR-012, contracts/container-image.md §Vulnerability guarantee)
- [X] T026 [US2] Run the vulnerability scan script against `tenancy-api:rc` and record the
  result (zero findings, or each finding's CVE and package) per SC-006 (depends on T025)

**Checkpoint**: User Stories 1 and 2 are both independently demonstrable

---

## Phase 5: User Story 3 - Establish a deployable-image baseline (Priority: P2)

**Goal**: A recorded, repeatable image-size and cold-start baseline with its measurement
conditions

**Independent Test**: Build the documented image from the same revision, repeat the baseline
procedure, and compare (spec.md US3)

- [X] T027 [US3] Write `infrastructure/scripts/measure-image-baseline.sh`: reports
  uncompressed size (`docker image inspect`), compressed size via an OCI export
  (`docker buildx build --output type=oci,dest=img.tar`, sum manifest layer sizes) plus the
  `docker save | gzip | wc -c` approximation labelled as such, `docker history --no-trunc`
  for the largest layers, and cold-start-to-ready (poll `/health/ready`) as median and p90
  over ≥10 runs with the first discarded (contracts/baseline-record.md, research.md R6)
- [X] T028 [US3] Run `measure-image-baseline.sh` against `tenancy-api:rc` and write
  `docs/operations/container-image-baseline.md` from its output, adding revision, working-tree
  state, image digest, base-image digest, and the conditions the script cannot know (host
  spec, Docker VM allocation, emulation, `--cpus`/`--memory` limits, whether the database was
  already healthy, `ASPNETCORE_ENVIRONMENT`, battery/thermal state) per
  contracts/baseline-record.md (depends on T027)

**Checkpoint**: All three user stories are independently functional and demonstrable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm nothing regressed and both developer workflows still work

- [X] T029 [P] Run `dotnet test` and confirm unit, integration, architecture, and
  tenant-isolation tests all pass, including T010, T011, and T018 (quickstart.md §7)
- [X] T030 [P] Confirm the `dotnet run` workflow still works unchanged: start
  `deploy/otel-collector/docker-compose.yml` alone, then `dotnet run --project
  src/Tenancy/Tenancy.Api` with .NET User Secrets (quickstart.md §8)
- [X] T031 Update roadmap.md's S5 row and *Done when* checklist, and AGENTS.md, to reflect
  the completed slice

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001, T002, T003 can start immediately and run in
  parallel
- **Foundational (Phase 2)**: T004 depends on T003; T009 depends on T004. T005 has no
  dependency; T006 and T007 depend on T005. T008 is independent. **Blocks all user stories.**
- **User Story 1 (Phase 3)**: Depends on Foundational (needs the built image, T009). No
  dependency on US2 or US3
- **User Story 2 (Phase 4)**: T018, T022, and T025 need only Foundational; T019–T021 depend
  on the `api` service existing in `compose.yaml` (T013, from US1) because there is nothing
  to inspect otherwise. Independently testable once that exists
- **User Story 3 (Phase 5)**: Depends on Foundational (needs `tenancy-api:rc` to exist, built
  the same way as US1/US2's image)
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Parallel Opportunities

- T001, T002, T003 together
- T010, T011 together (different test files, both depend only on Phase 2's T005–T007)
- T018, T022, T025 together (different files, no shared dependency)
- T029, T030 together

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 → Phase 2 (draining state, probe, image) → Phase 3 (compose stack)
2. **STOP and VALIDATE**: quickstart.md §1 end to end
3. This is a demoable local stack even before US2's security proofs and US3's baseline exist

### Incremental Delivery

1. Setup + Foundational → image builds, readiness/shutdown mechanics proven at unit level
2. Add US1 → `docker compose up` works, collector-outage-tolerant → demo
3. Add US2 → non-root and shutdown proven at the container level, secret scan proven able to
   fail → demo
4. Add US3 → baseline recorded → slice complete
