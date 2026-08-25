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
