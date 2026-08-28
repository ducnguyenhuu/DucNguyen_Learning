# Research: Observability

All three clarification-session unknowns (sampling rate, audit retention, health-check
interval) were already resolved in `spec.md`'s Clarifications section before this
phase started. The decisions below are implementation-approach research, not
requirement clarifications.

## R1: OpenTelemetry package set and exporter

**Decision**: Use the official `OpenTelemetry.Extensions.Hosting` package (registers
tracing/metrics/logging providers via `IServiceCollection`), with
`OpenTelemetry.Instrumentation.AspNetCore` (auto-instruments incoming HTTP requests —
gives the entry-point span and correlation ID for free) and
`OpenTelemetry.Instrumentation.SqlClient` (auto-instruments EF Core's underlying
ADO.NET calls as child spans). Export via `OpenTelemetry.Exporter.OpenTelemetryProtocol`
(the OTLP exporter) pointed at an OTel Collector endpoint read from configuration.

**Rationale**: This is the combination ADR-011 already specifies (OpenTelemetry SDK,
OTLP export, never a vendor SDK). Auto-instrumentation for ASP.NET Core and SqlClient
covers the two boundaries every request in this codebase crosses (HTTP in, SQL out)
without hand-writing span creation for every existing endpoint — hand-instrumenting
would mean touching every endpoint file for a slice whose main additions are structural.

**Alternatives considered**:
- **New Relic .NET agent**: rejected outright — ADR-018 explicitly forbids it; the
  point of the OTLP exporter is that the backend can change without touching code.
- **Application Insights SDK direct**: rejected for the same reason (ADR-011); App
  Insights remains a possible *secondary* OTLP-reached exporter in S6, out of scope
  here.
- **Manual span creation everywhere**: rejected as disproportionate effort for what
  auto-instrumentation already covers; manual spans are still added where a use case's
  own logic (not an HTTP/SQL boundary) needs a named operation — e.g. wrapping a
  multi-step use case in its own span for readability in the trace tree.

## R2: Enforcing the audit log's append-only property

**Decision**: A SQL Server `AFTER UPDATE, DELETE` trigger on the `AuditEntries` table
that always raises an error, added in the same EF Core migration that creates the
table. The application's own DbContext gets no `Update`/`Remove` DbSet operations
wired for this entity at all (belt-and-suspenders: the code path doesn't exist, and
even if it somehow did, the database refuses).

**Rationale**: FR-011 requires this to be "a structural property of the store's own
access surface, not a convention application code chooses to follow." A database
trigger is enforced regardless of which code, tool, or future developer touches the
table — including a hand-run `UPDATE` statement in a DBA session, which an
application-layer-only guard (e.g. an EF Core interceptor blocking the operation)
would not catch.

**Alternatives considered**:
- **EF Core `SaveChangesInterceptor`** (the same pattern `TenantSaveChangesInterceptor`
  already uses in this codebase): rejected as the *sole* mechanism — it only guards
  calls that go through this specific DbContext instance. A trigger is strictly
  stronger and costs one migration.
- **Revoking `UPDATE`/`DELETE` grants on the table for the application's DB
  principal**: a legitimate alternative with the same structural guarantee. Deferred
  in favor of a trigger because grant management sits outside EF Core migrations and
  would need separate infrastructure-as-code (Terraform) work to apply consistently
  across environments; a trigger travels with the schema migration itself. Worth
  revisiting if the DB-principal-permission model matures in a later slice.

## R3: Health check implementation

**Decision**: ASP.NET Core's built-in `Microsoft.Extensions.Diagnostics.HealthChecks`
middleware, with the community `AspNetCore.HealthChecks.SqlServer` package for the
database dependency check, exposed at two conventional routes: `/health/live`
(process is running — no dependency check) and `/health/ready` (dependency check
included, reflects the three-state model FR-008 requires).

**Rationale**: This is the standard, first-party mechanism for .NET/ASP.NET Core and
integrates directly with Kubernetes-style liveness/readiness probe conventions,
matching the 30-second polling interval clarified in the spec. Splitting live/ready
into two routes is the established convention for distinguishing "process up" from
"process up AND dependencies reachable" — exactly FR-008's three states (healthy /
unhealthy / not-yet-ready), where "not-yet-ready" is naturally `/health/ready`
returning its startup-incomplete state before the first successful dependency check.

**Alternatives considered**:
- **A single combined health endpoint**: rejected — conflates "should this pod be
  restarted" (liveness) with "should this pod receive traffic" (readiness), which
  Kubernetes' own probe model deliberately separates; collapsing them back into one
  endpoint would require the infrastructure layer (a later slice) to work around it.
- **A hand-rolled health-check controller**: rejected as reinventing what the
  first-party package already does correctly, for no gain.

## R4: Local Collector for offline development

**Decision**: A Docker Compose service running the official `otel/opentelemetry-collector`
image, configured to receive OTLP and export to its console/stdout (for a developer to
see spans/logs directly) as the default local target. Switching to the hosted New
Relic OTLP endpoint is a configuration change (the exporter's target URL), matching
`Tenancy.IntegrationTests`' existing Testcontainers-based local-infrastructure
convention.

**Rationale**: FR-014/SC-006 require switching between local-only and
backend-connected operation via configuration alone. A local Collector is the
standard OpenTelemetry pattern for this — the application never talks to New Relic
directly either way; it always talks to *a* Collector endpoint, and only the
Collector's own export target changes.

**Alternatives considered**:
- **Application exports directly to New Relic in all environments, no local
  Collector**: rejected — this would require network access to an external paid
  service for any local development involving telemetry, which User Story 4
  explicitly asks to avoid.
- **A hosted, always-on shared dev Collector**: rejected as unnecessary
  infrastructure for what a one-line Docker Compose service already solves locally.

## R5: Writing the audit entry atomically with the action it records

**Decision**: `IAuditWriter.RecordAsync(...)` stages an `AuditEntry` into the same
`TenancyDbContext` change tracker as the use case's own entity changes, so a single
`SaveChangesAsync()` call persists both — no separate transaction, no two-phase
commit. If the save fails, neither the action's state change nor its audit entry is
persisted.

**Rationale**: FR-012 requires the action and its audit entry to be "a single durable
unit." Using the same `DbContext`/`SaveChangesAsync` call is the simplest mechanism
that guarantees this — EF Core already wraps a single `SaveChangesAsync()` call in one
database transaction by default. This mirrors this codebase's existing precedent
(`TenantSaveChangesInterceptor` stamps tenant-owned entities inside the same save
call that persists them).

**Alternatives considered**:
- **A separate audit-writing service call, invoked after the main save succeeds**:
  rejected — this is exactly the "two independent, best-effort steps" the spec's edge
  cases explicitly rule out; a crash between the two steps would silently lose the
  audit trail for a real change.
- **An outbox pattern (write an audit "intent" row, process it asynchronously)**:
  rejected as disproportionate for this slice — outbox patterns solve cross-service
  consistency problems (roadmap S8's messaging work), and this audit write never
  leaves the same database or the same `SaveChangesAsync()` call.
