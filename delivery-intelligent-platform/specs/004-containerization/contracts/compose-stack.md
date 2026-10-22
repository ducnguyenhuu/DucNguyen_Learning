# Contract: Local Composed Stack

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Research**: [../research.md](../research.md)

`compose.yaml` at the repository root. FR-003 requires **exactly three** services: the
tenant service, its database, and the existing local telemetry collector. Nothing else.

## The one command

```bash
docker compose up --build --wait
```

`--wait` blocks until every service with a healthcheck reports healthy, which makes "the
stack is up" a machine-checkable fact rather than a judgement about scrolling logs.

## Services

### `sqlserver`

| Aspect | Value |
|---|---|
| Image | `mcr.microsoft.com/mssql/server:2022-latest` |
| Platform | `linux/amd64`, pinned explicitly — the image is amd64-only and runs under emulation on Apple Silicon (research.md R2) |
| Environment | `ACCEPT_EULA=Y`, `MSSQL_PID=Developer`, `MSSQL_SA_PASSWORD=${MSSQL_SA_PASSWORD:?...}` |
| Data | named volume, so `docker compose down` keeps the database and `down -v` resets it |
| Healthcheck | `/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -C -Q 'SELECT 1' -b`. The versioned tools path and `-C` (trust the self-signed certificate) are both required by current images |
| Start period | generous (~30 s) — under emulation first start is slow, and a too-short `start_period` reads as a broken stack |

### `otel-collector`

| Aspect | Value |
|---|---|
| Definition | `extends` the existing `deploy/otel-collector/docker-compose.yml` service, so the collector configuration has exactly one definition and the two workflows cannot drift |
| Config | the existing `deploy/otel-collector/config.yaml`, bind-mounted read-only, unchanged by this slice |
| Ports | 4317 (OTLP gRPC), 4318 (OTLP HTTP) |
| Dependency direction | **none**. Nothing depends on the collector being healthy — FR-006 and SC-005 require the service to be ready and functional without it |

### `api`

| Aspect | Value |
|---|---|
| Build | the root `Dockerfile`, context the repository root |
| Depends on | `sqlserver` with `condition: service_healthy` |
| Ports | `8080:8080` |
| Environment | `ConnectionStrings__TenancyDb` (interpolated, includes `Encrypt=True;TrustServerCertificate=True` for the container's self-signed certificate), `AzureAd__*`, `Observability__OtlpEndpoint=http://otel-collector:4317`, `ASPNETCORE_ENVIRONMENT=Development` |
| `read_only` | `true`, with `tmpfs: [/tmp]` |
| `stop_grace_period` | `45s` — must exceed the 15 s drain plus the OpenTelemetry flush tail (research.md R4). Compose's default is 10 s, which would be too short |
| Healthcheck | inherited from the image's `HEALTHCHECK`; not redefined here |

## Variable contract (`.env`)

Compose reads `.env` from the project directory automatically and uses it for interpolation.
`.gitignore` already excludes `.env`/`.env.*` with an `!.env.example` exception, so no
ignore-rule change is needed.

| Variable | Required | Notes |
|---|---|---|
| `MSSQL_SA_PASSWORD` | yes | ≥8 characters from three of the four character classes, or the SQL Server container exits at startup. State this in `.env.example` — the failure otherwise looks like a broken image |
| `AZURE_AD_TENANT_ID` | for authenticated scenarios | Maps to `AzureAd__TenantId` |
| `AZURE_AD_CLIENT_ID` | for authenticated scenarios | Maps to `AzureAd__ClientId` |
| `AZURE_AD_AUDIENCE` | for authenticated scenarios | Maps to `AzureAd__Audience` |
| `SAMPLE_RATE` | no | Existing collector variable; defaults to 10 |

Every required variable is referenced as `${VAR:?message}`. Compose then exits with that
message when the variable is unset or empty, which is the behaviour FR-008 and the spec's
second edge case ask for: identify the missing prerequisite, never fall back to a default
credential.

`.env.example` is committed, names every variable, and contains **no value** — not even a
placeholder that looks like a password, since a plausible-looking default is the thing people
copy and keep.

## Ordering and failure behaviour

| Situation | Required behaviour | Requirement |
|---|---|---|
| Database still starting | `api` is not started until `sqlserver` is healthy; once started, `/health/ready` stays 503 until migrations finish | FR-005, edge case 1 |
| Collector unavailable | `api` still becomes ready; authenticated tenant operations still succeed; the loss is visible in logs | FR-006, SC-005 |
| `MSSQL_SA_PASSWORD` unset | `docker compose up` fails immediately with the message from `${VAR:?}` | FR-008, edge case 2 |
| `docker compose down` during a request | SIGTERM, drain within 15 s, clean exit inside the 45 s grace period, no lost acknowledged mutation or audit entry | FR-007, SC-002 |

## Explicitly not in this file

No Kubernetes manifest, Helm chart, registry reference, image push, ingress, replica count,
resource request/limit for a scheduler, or production profile. `deployment/kubernetes/` and
`deployment/helm/` stay empty until S6. Compose profiles for future environments are not
added either — a second profile would be the speculative generality Principle X prohibits.
