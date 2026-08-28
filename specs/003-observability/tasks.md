---

description: "Task list for the Observability slice (003)"
---

# Tasks: Observability

**Input**: Design documents from `/specs/003-observability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/health-endpoints.md, quickstart.md

**Tests**: Included — spec 003 requires proving each structural guarantee (append-only
trigger, no-vendor-SDK gate, tenant-never-a-metric-dimension) under failure conditions,
per `testing` skill and Constitution Principle VII. Test tasks are not optional here.

**Organization**: Tasks are grouped by user story (US1–US4, in spec.md priority order),
after a Setup phase and a Foundational phase that every story depends on.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 — omitted for Setup, Foundational, and Polish tasks

## Path Conventions

Single service, existing four-project layout under `src/Tenancy/`; tests under
`tests/ArchitectureTests/`, `tests/Tenancy.UnitTests/`, `tests/Tenancy.IntegrationTests/`
(all existing projects — no new test project).

---

## Phase 1: Setup

**Purpose**: Add the packages and local infrastructure every story depends on.

- [ ] T001 Add `OpenTelemetry`, `OpenTelemetry.Extensions.Hosting`,
  `OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.SqlClient`,
  `OpenTelemetry.Exporter.OpenTelemetryProtocol` package references to
  `src/Tenancy/Tenancy.Infrastructure/Tenancy.Infrastructure.csproj`
- [ ] T002 Add `Microsoft.Extensions.Diagnostics.HealthChecks` and
  `AspNetCore.HealthChecks.SqlServer` package references to
  `src/Tenancy/Tenancy.Api/Tenancy.Api.csproj`
- [ ] T003 [P] Create the local OTel Collector Docker Compose service at
  `deploy/otel-collector/docker-compose.yml` and its config at
  `deploy/otel-collector/config.yaml` (OTLP receiver → console/stdout exporter, per
  research.md R4)

**Checkpoint**: Solution restores; local Collector can be started with
`docker compose -f deploy/otel-collector/docker-compose.yml up -d`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `AuditEntry` entity, its port, its append-only storage, and the OTel
SDK registration point that every user story's tasks build on.

**⚠️ CRITICAL**: No user story task may start until this phase is complete.

- [ ] T004 [P] Create `AuditEntryId` strongly-typed ID (`Guid`-backed, per this
  codebase's existing convention) in `src/Tenancy/Tenancy.Domain/Abstractions/Ids.cs`
- [ ] T005 [P] Create the `AuditEntry` entity (`Id`, `TenantId?`, `ActorUserId?`,
  `Action`, `ResourceType`, `ResourceId`, `OccurredAtUtc` from `IClock`) in
  `src/Tenancy/Tenancy.Domain/Auditing/AuditEntry.cs`, per data-model.md
- [ ] T006 [US-independent] Unit test: `AuditEntry` construction rejects empty
  `Action`/`ResourceType`/`ResourceId`, and permits both `TenantId` and `ActorUserId`
  null (unauthenticated-refusal case) in
  `tests/Tenancy.UnitTests/Auditing/AuditEntryTests.cs` — write first, watch it fail,
  then implement T005 to pass it
- [ ] T007 Declare `IAuditWriter.RecordAsync(AuditEntry entry, CancellationToken ct)` in
  `src/Tenancy/Tenancy.Application/Abstractions/IAuditWriter.cs` (depends on T005)
- [ ] T008 Add `DbSet<AuditEntry>` and an `IEntityTypeConfiguration<AuditEntry>` to
  `TenancyDbContext`, with no `Update`/`Remove` DbSet operations wired for this entity
  (depends on T005, T007)
- [ ] T009 Implement `AuditWriter : IAuditWriter` in
  `src/Tenancy/Tenancy.Infrastructure/Persistence/AuditWriter.cs` — stages the entry
  into the same `TenancyDbContext` change tracker as the caller's own changes; no
  separate `SaveChangesAsync()` call (depends on T008; research.md R5)
- [ ] T010 Add the EF Core migration creating `AuditEntries` plus a SQL Server
  `AFTER UPDATE, DELETE` trigger that always raises an error, in
  `src/Tenancy/Tenancy.Infrastructure/Migrations/` (depends on T008; research.md R2)
- [ ] T011 Integration test: direct `UPDATE` and direct `DELETE` against `AuditEntries`
  (bypassing the application, real SQL Server container) are both rejected by the
  database in
  `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs` — write first,
  watch it fail (no trigger yet), then apply T010 to pass it
- [ ] T012 Register `IAuditWriter` → `AuditWriter` scoped to match `TenancyDbContext`'s
  own scoped lifetime, in `src/Tenancy/Tenancy.Api/Program.cs`
- [ ] T013 [P] Create `OpenTelemetryExtensions` (one place wiring tracing, metrics, and
  logging providers plus the OTLP exporter, target endpoint from configuration) in
  `src/Tenancy/Tenancy.Infrastructure/Observability/OpenTelemetryExtensions.cs`
  (depends on T001)
- [ ] T014 Call `OpenTelemetryExtensions`'s registration from
  `src/Tenancy/Tenancy.Api/Program.cs` (depends on T013)

**Checkpoint**: `AuditEntries` exists and is provably append-only; OTel SDK registers
without error; no user story implementation has started yet.

---

## Phase 3: User Story 1 - Diagnose a failure from telemetry alone (P1) 🎯 MVP

**Goal**: Every request carries one correlation identifier across every span and log
line it produces; tenant/user identity enriches spans and logs (never metrics); tail
sampling keeps 100% of error traces.

**Independent Test** (spec.md): trigger a request that fails partway through, then
reconstruct its full server-side story using only its correlation identifier.

### Tests for User Story 1

- [ ] T015 [P] [US1] Integration test: a request spanning an internal SQL call produces
  one connected trace (HTTP span + SQL span share a trace ID) in
  `tests/Tenancy.IntegrationTests/Observability/CorrelationIdPropagationTests.cs` —
  write first, watch it fail
- [ ] T016 [P] [US1] Integration test: the structured log line for a request carries
  the same trace ID as its corresponding span, in the same file as T015 — write first,
  watch it fail
- [ ] T017 [P] [US1] Architecture test: no project references a vendor telemetry
  SDK/agent package (e.g. a New Relic-branded package) outside the OTLP exporter, in
  `tests/ArchitectureTests/TelemetryVendorGates.cs` — write first, watch it fail by
  temporarily adding a disallowed reference, then revert
- [ ] T018 [P] [US1] Test: a metric recorded by the application never carries a
  `tenant.id`/`user.id` tag — targeted unit test over the metrics-recording code (or an
  architecture-test scan of metric-tag literals) in
  `tests/ArchitectureTests/TelemetryVendorGates.cs` — write first, watch it fail by
  temporarily tagging a metric with tenant identity, then revert

### Implementation for User Story 1

- [ ] T019 [US1] Configure ASP.NET Core auto-instrumentation
  (`OpenTelemetry.Instrumentation.AspNetCore`) and SQL Client auto-instrumentation
  (`OpenTelemetry.Instrumentation.SqlClient`) inside `OpenTelemetryExtensions` (depends
  on T013; makes T015 pass)
- [ ] T020 [US1] Configure the correlation identifier: accept a valid incoming W3C
  Trace Context header, generate fresh otherwise (malformed input is discarded, not
  propagated) — `Activity.Current`'s existing `TraceId` via ASP.NET Core's built-in W3C
  propagator, no new type — verify in `OpenTelemetryExtensions` or a small
  `Program.cs` wire-up (depends on T019; makes T015 pass; spec edge case: malformed
  correlation ID)
- [ ] T021 [US1] Wire the trace ID into every structured log line (logging provider
  registered via `OpenTelemetryExtensions`, or `Activity.Current`-based enricher on the
  existing logging pipeline) (depends on T019, T020; makes T016 pass)
- [ ] T022 [US1] Add tenant/user identity as span and log attributes wherever known at
  emission time (existing `ITenantContext`, whatever is known for an unauthenticated
  refusal is fine — no blocking) in the request pipeline (depends on T019; spec edge
  case: unauthenticated caller enrichment)
- [ ] T023 [US1] Configure tail-based sampling: 100% retention for error/failed-request
  traces, default 10% for successful-request traces, both configurable, inside
  `OpenTelemetryExtensions` (depends on T019; makes SC of retained error traces true)
- [ ] T024 [US1] Configure the OTLP exporter's fire-and-forget behavior — an export
  failure or backend unavailability must not fail, block, or measurably slow a request
  — inside `OpenTelemetryExtensions` (depends on T013; spec edge case: telemetry
  backend unreachable at runtime)
- [ ] T025 [US1] Ensure metrics recorded by the application use only bounded
  dimensions (never raw tenant/user identity) — review/adjust any metric-recording code
  this slice introduces or touches (depends on T018)

**Checkpoint**: A failing request is fully diagnosable end-to-end from its correlation
identifier alone; T015–T018 all pass.

---

## Phase 4: User Story 2 - Know a service is healthy without asking a human (P1)

**Goal**: `/health/live` and `/health/ready` report the three states FR-008 requires.

**Independent Test** (spec.md): query the health endpoint with the database
unavailable and confirm the response reflects the unhealthy dependency.

### Tests for User Story 2

- [ ] T026 [P] [US2] Integration test: `/health/live` returns 200 always (process up),
  in `tests/Tenancy.IntegrationTests/Observability/HealthCheckTests.cs` — write first,
  watch it fail
- [ ] T027 [P] [US2] Integration test: `/health/ready` returns 200 Healthy with SQL
  Server reachable, and 503 Unhealthy naming `"sqlserver"` once the SQL Server
  container is stopped, in the same file as T026 — write first, watch it fail

### Implementation for User Story 2

- [ ] T028 [US2] Register `Microsoft.Extensions.Diagnostics.HealthChecks` with the
  `AspNetCore.HealthChecks.SqlServer` check for `TenancyDbContext`'s connection, in
  `src/Tenancy/Tenancy.Api/Program.cs` (depends on T002)
- [ ] T029 [US2] Implement `HealthCheckResponseWriter` shaping the JSON response body
  per contracts/health-endpoints.md (status + checks array with name/status/description)
  in `src/Tenancy/Tenancy.Api/HealthChecks/HealthCheckResponseWriter.cs`
- [ ] T030 [US2] Map `GET /health/live` (no dependency check) and `GET /health/ready`
  (dependency check included, using `HealthCheckResponseWriter`) in
  `src/Tenancy/Tenancy.Api/Program.cs` (depends on T028, T029; makes T026, T027 pass)

**Checkpoint**: Stopping the SQL Server container flips `/health/ready` to 503 within
one health-check interval, while `/health/live` still reports healthy; T026–T027 pass.

---

## Phase 5: User Story 3 - Prove a security-/tenant-relevant action happened (P2)

**Goal**: Every tenant-mutating action and every security-relevant authorization
refusal produces a durable, append-only audit entry, written atomically with the
action.

**Independent Test** (spec.md): perform a tenant-mutating action, confirm a
corresponding audit entry exists and is retrievable, and that no application code path
can modify or delete it (T011 already proves the last part structurally).

### Tests for User Story 3

- [ ] T031 [P] [US3] Integration test: removing a membership produces exactly one
  `AuditEntry` with matching actor/action/resource/tenant, persisted in the same
  transaction as the removal (simulate a post-removal-write failure and confirm neither
  side persists), in
  `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs` — write first,
  watch it fail
- [ ] T032 [P] [US3] Integration test: an authorization refusal already logged per spec
  001 FR-025 also produces a matching audit entry, in the same file as T031 — write
  first, watch it fail

### Implementation for User Story 3

- [ ] T033 [US3] Call `IAuditWriter.RecordAsync(...)` from
  `src/Tenancy/Tenancy.Application/Members/RemoveMember.cs` before its own
  `SaveChangesAsync()` (same change tracker, same call), action id
  `"membership.removed"` (depends on T007, T009)
- [ ] T034 [P] [US3] Call `IAuditWriter.RecordAsync(...)` from
  `src/Tenancy/Tenancy.Application/Members/ChangeMemberRole.cs`, action id
  `"membership.role_changed"` (depends on T007, T009)
- [ ] T035 [P] [US3] Call `IAuditWriter.RecordAsync(...)` from
  `src/Tenancy/Tenancy.Application/Invitations/InviteMember.cs`,
  `AcceptInvitation.cs`, and `RevokeInvitation.cs`, action ids
  `"invitation.issued"` / `"invitation.accepted"` / `"invitation.revoked"` (depends on
  T007, T009)
- [ ] T036 [P] [US3] Call `IAuditWriter.RecordAsync(...)` from
  `src/Tenancy/Tenancy.Application/Tenants/RenameTenant.cs`, action id
  `"tenant.renamed"` (depends on T007, T009)
- [ ] T037 [US3] Call `IAuditWriter.RecordAsync(...)` from the existing
  authorization-refusal logging path (spec 001 FR-025) for security-relevant refusals,
  action id `"authorization.refused"`, tolerating null `TenantId`/`ActorUserId` when
  unresolved (depends on T007, T009; spec edge case: audit storage unavailable during
  a mutating action — the action must not be treated as complete if the audit write
  fails)

**Checkpoint**: Every FR-010-listed action writes a durable audit entry in the same
unit of work; T031–T032 pass; T011 (Foundational) already proves append-only.

---

## Phase 6: User Story 4 - Work with telemetry offline (P3)

**Goal**: The system is fully usable — traces, metrics, logs all visible — with the
external telemetry backend unreachable, using only the local Collector from T003.

**Independent Test** (spec.md): run with network access to the external backend
blocked, confirm the local Collector still receives and displays telemetry.

### Tests for User Story 4

- [x] T038 [US4] Quickstart-driven manual verification: follow
  `specs/003-observability/quickstart.md` §1–2 with the local Collector as the only
  configured exporter target and no route to any external endpoint; confirm spans and
  correlated logs appear in the Collector's console output

### Implementation for User Story 4

- [x] T039 [US4] Default `OpenTelemetryExtensions`'s exporter endpoint to the local
  Collector (`deploy/otel-collector/`) via configuration, with the New Relic endpoint
  as an alternative value only (never a code branch) — confirm switching between them
  needs no code change (depends on T013, T003; makes SC-006 true)
- [x] T039a [US4] Read the New Relic OTLP endpoint URL and ingest API key through
  `IConfiguration` only — never hardcoded, never added to
  `src/Tenancy/Tenancy.Api/appsettings.json` or `appsettings.Development.json`; set the
  local override via .NET User Secrets (existing convention, matching how the SQL
  Server connection string is handled). Add a code comment or a short note in
  `quickstart.md` §6 stating that non-local deployment reads the same key from Azure
  Key Vault once this service is deployed to AKS, per Constitution Principle V (depends
  on T039)

**Checkpoint**: Local-only operation and hosted-backend operation are behaviorally
identical, differing only by configuration; T038 passes by inspection.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all four stories.

- [ ] T040 [P] Run the full `quickstart.md` walkthrough (§1–6) end-to-end, including
  the §5 "prove every gate can fail" table, and record results
- [ ] T041 [P] Update `AGENTS.md`'s "Current state" section: mark slice 003
  (Observability) complete, matching the convention used for prior slices
- [ ] T042 Run the complete test suite (unit + integration + architecture) and confirm
  all requirement-to-test mappings for FR-001–FR-014/FR-013a exist (extend
  `RequirementCoverageGates.cs`'s convention if this slice adopts `[CoversRequirement]`
  attributes, or record the mapping in `quickstart.md`/spec.md notes if not)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T007–T009,
  T013 in particular are load-bearing for every story below)
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only — independent of US1
- **User Story 3 (Phase 5)**: Depends on Foundational only — independent of US1/US2,
  but touches use-case files US1/US2 do not touch, so no file conflict
- **User Story 4 (Phase 6)**: Depends on Foundational (T003, T013) — behaviorally
  layers on US1's exporter wiring, but is a configuration/verification task, not a
  code dependency on US1's other tasks
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Parallel Opportunities

- T004, T005 (Foundational entity/ID) in parallel with T013 (OTel wiring) — disjoint
  files
- Within US1: T015–T018 (tests) in parallel with each other
- Within US3: T034, T035, T036 (different use-case files) in parallel once T007/T009
  exist
- US2 (Phase 4) can proceed in parallel with US1 (Phase 3) once Foundational is done —
  disjoint files (`HealthChecks/` vs. tracing wiring)

---

## Implementation Strategy

### MVP First

US1 + US2 (both P1) together form the MVP: a service that is diagnosable from
telemetry and reports its own health. US3 (audit) and US4 (offline collector) are
valuable but not required to demonstrate the slice's core diagnosability goal.

### Notes on requirements not independently task-covered

- **FR-002** (correlation ID across every service-to-service/messaging boundary): not
  independently testable in this slice — `Tenancy` is still the only service and no
  messaging boundary exists yet (per plan.md's Scale/Scope). FR-002 is satisfied
  vacuously today; it becomes testable the moment a second service or a message queue
  is introduced (roadmap S8+), at which point a task should be added there to prove it.
- **FR-013** (audit log is a separate concern from general logging): satisfied by
  construction — `AuditEntry` is written only via `IAuditWriter` (T007–T009), never
  through the general `ILogger` pipeline — no dedicated task asserts this separation
  because there is no shared code path that could accidentally merge them.

### Incremental Delivery

1. Setup + Foundational → foundation ready (append-only audit storage proven, OTel SDK
   registers)
2. US1 → correlated traces/logs/sampling → validate independently
3. US2 → health checks → validate independently (MVP complete after US1+US2)
4. US3 → immutable audit log wired into real use cases → validate independently
5. US4 → confirm offline/local-only operation → validate independently
6. Polish → full quickstart walkthrough, requirement coverage check
