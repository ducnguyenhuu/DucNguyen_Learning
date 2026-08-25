# Implementation Plan: Observability

**Branch**: `003-observability` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-observability/spec.md`

## Summary

Instrument the existing `Tenancy` service (the only service that exists yet) with
OpenTelemetry traces/metrics/logs exported over OTLP to a local Collector by default,
correlation ID propagation via W3C Trace Context, tenant/user identity on spans and
logs only (never metrics), tail-based sampling (100% error traces, 10% default for
successful traces), ASP.NET Core health checks covering the service's SQL Server
dependency, and a new append-only `AuditEntries` table enforced at the database level
(a trigger rejecting `UPDATE`/`DELETE`) written in the same transaction as the
tenant-mutating action it records. New Relic (ADR-018) is one exporter target,
configured, not coded to.

## Technical Context

**Language/Version**: .NET 10, C# (matches ADR-002; no change from slices 001-002)
**Primary Dependencies**: `OpenTelemetry`, `OpenTelemetry.Extensions.Hosting`,
`OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.SqlClient`,
`OpenTelemetry.Exporter.OpenTelemetryProtocol` (OTLP exporter — backend-agnostic;
reaches New Relic per ADR-018 through OTLP, never a New Relic SDK), ASP.NET Core's
built-in `Microsoft.Extensions.Diagnostics.HealthChecks` plus
`AspNetCore.HealthChecks.SqlServer` for the dependency check
**Storage**: Azure SQL / SQL Server (existing `TenancyDbContext`) — a new
`AuditEntries` table in the same database, per Principle III (each service owns its
data exclusively; audit storage does not become a new service)
**Testing**: xUnit v3 + AwesomeAssertions (existing convention); architecture tests in
`tests/ArchitectureTests` for the new boundary this slice adds (no direct New Relic SDK
reference — OTLP exporter only); integration tests against a real SQL Server container
for the append-only trigger and the health-check dependency path
**Target Platform**: Linux container on AKS (existing), local dev via `dotnet run` +
local OTel Collector (Docker Compose, matching `Tenancy.IntegrationTests`' existing
Testcontainers convention)
**Project Type**: Single service (`Tenancy`) — this slice adds a cross-cutting concern
to the existing four-project structure, not a new service
**Performance Goals**: Telemetry emission adds no more than a few milliseconds of
request overhead (fire-and-forget per FR-006); health-check endpoint responds in
well under 1 second so it is safe to poll every 30 seconds (per the clarified interval)
**Constraints**: No vendor SDK/agent for telemetry (ADR-011/ADR-018 — OTLP exporter
only); tenant/user identity never as a metric dimension (New Relic per-day cardinality
limit); audit store's append-only guarantee must be structural (DB-enforced), not a
code convention; telemetry export failure must never fail or block a request
**Scale/Scope**: One service today (`Tenancy`); the instrumentation approach must
generalize to future services without rework, since ADR-011 commits to consistent
instrumentation across every service as they arrive
**Secrets**: The New Relic OTLP endpoint URL and ingest API key are read via
`IConfiguration` like any other setting, but MUST NOT be committed to
`appsettings.json`/`appsettings.Development.json` — locally via .NET User Secrets
(existing convention), and via Azure Key Vault + workload identity once this service is
actually deployed non-locally (Principle V), matching the pattern already used for the
SQL Server connection string. No Key Vault or Terraform wiring exists in this repo yet
for *any* slice (`infrastructure/terraform/` is still empty) — provisioning that
infrastructure is out of scope for this slice and belongs to whichever slice first
deploys a service to AKS; this slice only ensures the code path never hardcodes or logs
the key, so it drops into that mechanism without rework.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I — Human approval for production/high-risk actions | N/A | This slice adds instrumentation and an audit store; no production deployment path or high-risk AI action is introduced |
| II — Architectural authority | ✅ Pass | ADR-011 (OpenTelemetry) and ADR-018 (New Relic backend) already settle the instrumentation/backend questions this slice implements; no new ADR needed unless design work surfaces a genuinely new decision |
| III — Business-capability boundaries | ✅ Pass | Audit storage lives inside `Tenancy`'s own database (`TenancyDbContext`), not a new shared service or store; no cross-service data access introduced |
| IV — Tenant isolation | ✅ Pass | Audit entries and traces carry tenant identity for diagnostic/compliance purposes but this slice does not add new tenant-scoped read paths; existing isolation gates (spec 002) are unaffected |
| V — Secure by default | ✅ Pass | FR-005 explicitly forbids secrets/unnecessary PII in telemetry; audit entries record actor/action/resource/time only, no credential material; the New Relic API key is never committed to `appsettings.json` — see Technical Context "Secrets" |
| VI — Observable by default | ✅ Pass (this slice's whole purpose) | Correlated traces/logs/metrics, health checks, immutable audit records — directly implements this principle's rules |
| VII — Automated gates over vigilance | ✅ Pass | A new architecture-test gate is planned: no direct New Relic (or other vendor) SDK/agent reference outside the OTLP exporter package, and the append-only property is proven by an integration test attempting `UPDATE`/`DELETE` against the audit table and expecting it to fail |
| VIII — Deterministic first | N/A | No AI capability in this slice |
| IX — AI provider abstraction | N/A | No AI invocation in this slice |
| X — Vertical slices | ✅ Pass | Ships working, tested, deployable instrumentation across a real service, not a technical layer with nothing observing it. Non-local exporter provisioning (Key Vault, Terraform) is explicitly deferred to the slice that first deploys to AKS — no infra-as-code exists yet for any service, so this is a pre-existing scope boundary, not one this slice introduces |
| XI — No individual measurement | ✅ Pass | Telemetry and audit entries record system/tenant/action facts, never used for individual developer evaluation |

No violations requiring justification. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/Tenancy/
├── Tenancy.Api/
│   ├── Program.cs                          # OTel SDK registration, health-check
│   │                                         mapping (existing file, extended)
│   ├── HealthChecks/
│   │   └── HealthCheckResponseWriter.cs    # New — shapes the health JSON response
│   └── ...                                  # existing endpoints, unchanged
├── Tenancy.Application/
│   └── Abstractions/
│       └── IAuditWriter.cs                 # New — port for writing an audit entry,
│                                              consumed by use cases that already
│                                              mutate tenant-scoped state
├── Tenancy.Domain/
│   └── Auditing/
│       └── AuditEntry.cs                   # New — the entity itself (actor, action,
│                                              resource, timestamp)
└── Tenancy.Infrastructure/
    ├── Observability/
    │   └── OpenTelemetryExtensions.cs      # New — one place wiring tracing/metrics/
    │                                          logging providers + OTLP exporter
    └── Persistence/
        ├── AuditWriter.cs                  # New — IAuditWriter implementation
        └── Migrations/
            └── ...AddAuditEntries.cs       # New EF Core migration: table +
                                               append-only trigger

tests/
├── ArchitectureTests/
│   └── TelemetryVendorGates.cs             # New — no direct New Relic (or other
│                                              vendor) SDK reference outside the
│                                              OTLP exporter package
├── Tenancy.UnitTests/
│   └── Auditing/
│       └── AuditEntryTests.cs              # New — entity construction/validation
└── Tenancy.IntegrationTests/
    ├── Observability/
    │   ├── HealthCheckTests.cs             # New — healthy / unhealthy (DB down) /
    │   │                                      not-ready
    │   └── CorrelationIdPropagationTests.cs # New — one connected trace across a
    │                                           request that spans an internal call
    └── Auditing/
        └── AuditEntryAppendOnlyTests.cs     # New — attempts UPDATE/DELETE against
                                                the real table, expects DB rejection

deploy/otel-collector/                       # New — local Collector config (Docker
└── config.yaml                              # Compose), OTLP receiver -> stdout/
                                                console exporter for offline dev,
                                                separate from the New Relic OTLP
                                                target used non-locally
```

**Structure Decision**: Single service (`Tenancy`), extending its existing four-project
layout. No new service is created — audit storage and telemetry wiring live inside the
service that already owns the data they describe, per Principle III. The
`OpenTelemetryExtensions` class centralizes SDK registration once, so a future second
service (per ADR-011's "consistent across every service as they arrive") can reuse the
same registration shape rather than reinventing it.
