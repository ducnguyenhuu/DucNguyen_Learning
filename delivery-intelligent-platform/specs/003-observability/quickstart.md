# Quickstart: Observability

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

## Prerequisites

| Requirement | Notes |
|---|---|
| .NET 10 SDK | Same as slices 001-002 |
| Docker Desktop or OrbStack | For the local OTel Collector (Docker Compose) and the existing SQL Server Testcontainer |

No New Relic account is required for local development — the default exporter target
is the local Collector.

## 1. Run with local telemetry only

```bash
docker compose -f deploy/otel-collector/docker-compose.yml up -d
dotnet run --project src/Tenancy/Tenancy.Api
```

Make a request against any existing endpoint (e.g. `GET /tenants`), then check the
Collector's console output — you should see a trace with at least two spans (the
incoming HTTP request, and the SQL query it triggered), both carrying the same trace
ID.

## 2. Verify correlation ID propagation

```bash
curl -i http://localhost:PORT/tenants
```

Check the structured log output for the same request — the log line's correlation
identifier (trace ID) must match the trace ID shown in the Collector's console
output for the corresponding span.

## 3. Verify health checks

```bash
curl -i http://localhost:PORT/health/live    # expect 200, {"status":"Healthy"}
curl -i http://localhost:PORT/health/ready   # expect 200 once DB is reachable

# Stop the SQL Server container, then:
curl -i http://localhost:PORT/health/ready   # expect 503, naming "sqlserver"
```

## 4. Verify the audit log is genuinely append-only

1. Perform a tenant-mutating action (e.g. remove a membership) via the API.
2. Query the `AuditEntries` table directly and confirm a row exists recording the
   action.
3. Attempt `UPDATE AuditEntries SET Action = 'tampered' WHERE Id = '<the row>'`
   directly against the database (not through the application). **Expect this to
   fail** — the trigger added in this slice's migration must reject it.
4. Attempt `DELETE FROM AuditEntries WHERE Id = '<the row>'`. **Expect this to fail**
   too.

## 5. Prove every gate can actually fail

Per FR-023's spirit (carried over from spec 002 — a gate that never could have failed
is decoration), each new gate in this slice should be proven red once before being
accepted:

| Gate | Introduce this violation | Expect |
|---|---|---|
| No vendor telemetry SDK | Add a direct reference to a New Relic .NET package (not the OTLP exporter) in any project | Architecture test fails, naming the project and package |
| Audit append-only | Run the manual `UPDATE`/`DELETE` steps in §4 above | Database rejects the statement — this is the gate, proven directly against the real table, not simulated |
| Tenant identity never a metric dimension | Add a metric with a `tenant.id` tag | Architecture test (or a targeted unit test over the metrics-recording code) fails, naming the offending metric |

## 6. Switch to the New Relic backend (non-local)

Change the OTLP exporter endpoint and ingest API key in configuration only — no code
change. `OpenTelemetryExtensions.cs` reads both via `IConfiguration`:

- `Observability:OtlpEndpoint` — the OTLP endpoint URL. Leave unset for local dev
  (the OpenTelemetry .NET SDK then defaults to `http://localhost:4317`, the local
  Collector); set it to New Relic's OTLP endpoint (`https://otlp.nr-data.net:4317`) to
  switch backends.
- `Observability:NewRelicApiKey` — New Relic's "Ingest - License Key". When present and
  non-empty, it is sent as the OTLP exporter's `api-key` header (New Relic's documented
  OTLP ingest convention). When absent (the local-dev default), no such header is added
  and the exporter talks to the local Collector exactly as before.

Set both locally via .NET User Secrets for the `Tenancy.Api` project — never in
`appsettings.json` or `appsettings.Development.json` (Constitution Principle V):

```bash
dotnet user-secrets set "Observability:OtlpEndpoint" "https://otlp.nr-data.net:4317" \
  --project src/Tenancy/Tenancy.Api
dotnet user-secrets set "Observability:NewRelicApiKey" "<your-ingest-license-key>" \
  --project src/Tenancy/Tenancy.Api
```

Confirm the same trace that appeared in the local Collector's console now appears in
New Relic's UI.

Once this service is actually deployed to AKS, the same two configuration keys are
resolved from Azure Key Vault via workload identity instead (Constitution Principle
V) — the `IConfiguration` read in `OpenTelemetryExtensions.cs` does not change, only
where the value comes from. Provisioning that Key Vault entry is out of scope for this
slice, since no Terraform exists yet for any service's non-local secrets; it belongs
to whichever slice first deploys a service to AKS.

## Requirement-to-test coverage

This slice's tests do not use the `[CoversRequirement]` attribute that
`tests/ArchitectureTests/RequirementCoverageGates.cs` enforces for spec 001. That gate is
explicitly scoped to spec 001's twenty-six requirements only (see its own class remarks) —
extending it here would also collide with FR numbering, since spec 003 reuses the same
`FR-001`–`FR-014` identifiers as spec 001 for entirely different requirements, and the
gate's scan has no notion of which spec a declaration belongs to. Recording the mapping
here, by hand, avoids that collision while keeping the record next to the quickstart a
developer already reads to exercise these requirements.

| Requirement | Exercised by |
|---|---|
| FR-001 (correlation identifier on every span/log line, W3C format) | `tests/Tenancy.IntegrationTests/Observability/CorrelationIdPropagationTests.cs`: `GetTenant_LogLine_CarriesSameTraceId_AsItsActivity`, `GetTenant_WithWellFormedTraceparentHeader_AdoptsSameTraceId` |
| FR-002 (correlation propagated across every boundary) | `tests/Tenancy.IntegrationTests/Observability/CorrelationIdPropagationTests.cs`: `GetTenant_ProducesOneConnectedTrace_AcrossHttpAndSqlActivities` (this slice has one service; the HTTP→SQL boundary is the only one that exists to test) |
| FR-003 (OpenTelemetry/OTLP only, no vendor SDK/agent) | `tests/ArchitectureTests/TelemetryVendorGates.cs`: `PackageVersions_ContainNoKnownTelemetryVendorSdkNamePattern` |
| FR-004 (tenant/user on spans/logs, never as a metric dimension) | `tests/Tenancy.IntegrationTests/Observability/TenantUserEnrichmentTests.cs` (enrichment present); `tests/ArchitectureTests/TelemetryVendorGates.cs`: `NoMetricRecordingCallIsFoundNearATenantOrUserIdentityTagLiteral` (never a metric dimension) |
| FR-005 (no secrets/PII in telemetry) | `tests/Tenancy.IntegrationTests/Scenarios/LogHygieneTests.cs`: `AuthenticatedRequest_NeverLogsBearerTokenOrSecretHeaderValues`; `tests/Tenancy.UnitTests/Architecture/SecretExclusionTests.cs` (same discipline spec 001's FR-025 established, extended to traces/metrics per FR-005's text) |
| FR-006 (telemetry failure never fails/blocks a request) | `tests/Tenancy.IntegrationTests/Observability/TelemetryResilienceTests.cs`: `GetTenant_SucceedsPromptly_EvenWhenOtlpExporterEndpointIsUnreachable` |
| FR-007 (tail-based sampling, 100% of errors, configurable default 10% of successes) | No test — this is delegated entirely to the Collector's `tail_sampling` processor config (`deploy/otel-collector/config.yaml`), not application code. The application's own obligation (never sample below 100% before the Collector decides) is documented and enforced by using `AlwaysOnSampler` in `OpenTelemetryExtensions.cs`, but no automated test asserts the Collector's YAML policy itself. **Gap, called out explicitly**: this requirement's Collector-side half is unverified by any test in this solution. |
| FR-008 (health surface: healthy/unhealthy/not-ready) | Healthy and unhealthy-dependency states: `tests/Tenancy.IntegrationTests/Observability/HealthCheckTests.cs`: `GetHealthLive_ReturnsHealthy`, `GetHealthReady_ReflectsSqlServerReachability`. Not-yet-ready state (the "startup" health check backed by `StartupState`): `tests/Tenancy.UnitTests/Observability/StartupHealthCheckTests.cs` only — this state cannot be observed end-to-end via HTTP in this codebase's test harness, since `Program.cs` marks startup ready before the server starts listening (see `HealthCheckTests`'s own remarks for why); the production logic is exercised at the unit level instead. |
| FR-009 (health reflects real dependency reachability) | `tests/Tenancy.IntegrationTests/Observability/HealthCheckTests.cs`: `GetHealthReady_ReflectsSqlServerReachability` |
| FR-010 (durable audit entry for tenant-mutating actions/refusals) | `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs`: `Delete_ActiveMember_ProducesExactlyOneMatchingAuditEntry`, `Post_Invitation_AsNonAdministrator_IsRefused_AndProducesMatchingAuditEntry`; `tests/Tenancy.UnitTests/Auditing/AuditEntryTests.cs` |
| FR-011 (append-only: no code path can update/delete) | `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs`: `DirectUpdateAndDelete_AgainstAuditEntries_AreBothRejectedByTheDatabase` |
| FR-012 (action + audit entry written as one durable unit) | `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs`: `Delete_SoleAdministrator_IsRefused_AndProducesNoAuditEntry`; `tests/Tenancy.UnitTests/Members/RemoveMemberTests.cs`, `tests/Tenancy.UnitTests/Invitations/InviteMemberTests.cs` (via `FakeAuditWriter`, asserting the audit call happens in the same operation) |
| FR-013 (audit log separate from general app logs; general logs not tamper-evident) | `tests/Tenancy.IntegrationTests/Auditing/AuditEntryAppendOnlyTests.cs` (append-only guarantee scoped to `AuditEntries` only) together with `tests/Tenancy.IntegrationTests/Scenarios/LoggingCoverageTests.cs` (general logs, no such guarantee asserted or implied) |
| FR-013a (indefinite retention, no deletion/archival mechanism) | No test — this is an absence-of-a-feature requirement (nothing to exercise). Confirmed instead by source inspection: no deletion/archival code path exists anywhere in `src/Tenancy` for `AuditEntries`, and FR-011's gate would fail if one were added via ordinary application code. |
| FR-014 (local Collector; switching backends is config-only) | `deploy/otel-collector/docker-compose.yml` + `deploy/otel-collector/config.yaml` (existence, exercised manually in §1 above); `OpenTelemetryExtensions.cs`'s `OtlpEndpointConfigurationKey`/`NewRelicApiKeyConfigurationKey` (no test asserts the New Relic switch itself, since that requires live New Relic credentials — see §6's static-only review note) |

Two genuine gaps exist, both called out above rather than papered over: FR-007's
Collector-side tail-sampling policy, and FR-014's New Relic backend switch, have no
automated test — both require infrastructure (a real Collector config under test, a real
New Relic account) that this solution's test suite does not exercise. Every other
requirement, FR-001 through FR-013a excluding those two Collector/backend-config halves,
has at least one test named above.
