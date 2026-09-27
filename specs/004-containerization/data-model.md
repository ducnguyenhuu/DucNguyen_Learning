# Phase 1 Data Model: Containerization

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

## No persisted entity changes

This slice adds no table, no column, no index, and no migration. The spec's assumptions say
so directly: the existing service, migrations, health endpoints, authentication, audit log,
and collector are the starting point and their business behaviour does not change. The
`AuditEntries` table and its append-only trigger from slice 003 are untouched; FR-007's
"without abandoning an acknowledged tenant mutation or its required audit entry" is a
guarantee about *shutdown timing*, satisfied by draining in-flight requests rather than by
any change to how an audit entry is written.

What this slice does introduce is three non-persisted models worth stating precisely, because
each one has an invariant that is easy to break silently.

---

## 1. Readiness lifecycle (in-process, `StartupState`)

A single process-wide state, currently two-valued, becoming three-valued. It is what
`/health/ready` reports through `StartupHealthCheck`, and therefore what the container's
`HEALTHCHECK` and Compose's `depends_on: condition: service_healthy` ultimately observe.

| State | Reported on `/health/ready` | Reported on `/health/live` | Set by |
|---|---|---|---|
| `Starting` | `Unhealthy` — "startup not yet complete" | `Healthy` | initial state |
| `Ready` | `Healthy` (if the SQL Server check also passes) | `Healthy` | `MarkReady()`, once, after startup work |
| `Draining` | `Unhealthy` — "shutting down", distinct wording from both above | `Healthy` | `MarkStopping()`, from `ApplicationStopping` |

**Transitions**: `Starting → Ready → Draining`, and also `Starting → Draining` — the spec's
third edge case (a termination signal arriving before readiness) requires that a container
which never became ready still shuts down cleanly without ever advertising readiness.

**Invariants**:
- Transitions are one-way and terminal at `Draining`. Once stopping, nothing returns the
  process to `Ready`, so a late-arriving `MarkReady()` must not resurrect readiness. This is
  the one real hazard in the change: `Program.cs` calls `MarkReady()` unconditionally after
  its startup work, and a SIGTERM during startup makes those two calls race.
- Liveness never depends on this state. A draining container must not look dead, or an
  orchestrator restarts it mid-drain.
- The three readiness descriptions must be distinguishable by a human reading the response
  body — not-yet-started, dependency-unreachable, and draining are three different operational
  situations. Slice 003's `contracts/health-endpoints.md` already establishes that the body is
  for humans and the status code is for routers; this adds a third body case, not a third
  status code.
- Cross-thread visibility: the existing `volatile bool` pattern generalizes to a `volatile`
  enum or a second `volatile bool`; a lock is unnecessary because every transition is a single
  write, but a read-modify-write (such as "only mark ready if not stopping") is *not* a single
  write and must be written with that in mind.

---

## 2. Container runtime configuration contract

The set of inputs the image reads from its environment. Full detail, including which are
required, lives in [contracts/container-image.md](contracts/container-image.md); the model
matters here because of what the entries have in common.

| Key | Kind | Required | Source in the local stack |
|---|---|---|---|
| `ConnectionStrings__TenancyDb` | secret-bearing | yes | interpolated in `compose.yaml` from `.env` |
| `AzureAd__*` (instance, tenant id, client id, audience) | identity settings | yes for authenticated scenarios | `.env` |
| `Observability__OtlpEndpoint` | endpoint | no (defaults to the SDK's `localhost:4317`) | `compose.yaml`, pointing at the collector service |
| `Observability__NewRelicApiKey` | secret | no | unset locally |
| `ASPNETCORE_ENVIRONMENT` | environment selector | no (defaults to Production) | `compose.yaml` sets `Development` (research.md R3) |
| `ASPNETCORE_HTTP_PORTS` | listener port | no | inherited `8080` from the base image; do not set `ASPNETCORE_URLS` |

**Invariants**:
- Every secret-bearing key is absent from every tracked file and from every image layer *and*
  from the image config. `.env.example` names keys and holds no values.
- The double-underscore form is the section separator .NET configuration expects; it must map
  onto exactly the keys the existing code already reads (`ConnectionStrings:TenancyDb`,
  `AzureAd:*`, `Observability:*`). This slice introduces no new configuration key, which is
  what makes it a packaging change rather than a behaviour change.
- A missing required value fails the stack at startup with a readable message, never with a
  default. For `.env` interpolation that is `${VAR:?message}`; for the token-lifetime
  expectation the service already fails fast in `Program.cs`.
- Local SQL Server uses a self-signed certificate, so the connection string needs
  `Encrypt=True;TrustServerCertificate=True` — acceptable *only* because the endpoint is a
  container on the developer's own machine, and it must not become the shape of a deployed
  connection string.

---

## 3. Baseline record

The artifact FR-010 requires, written to `docs/operations/container-image-baseline.md`. It is
a document, not a database row, but it has a required field set — see
[contracts/baseline-record.md](contracts/baseline-record.md) for the field list and the
commands that produce each value.

**Invariants**:
- Every recorded number carries the command and flags that produced it. A size without a
  method is ambiguous by a factor of two to four, because compressed and uncompressed sizes
  differ by roughly that much (research.md R6).
- The image is identified by digest, not only by tag. The same tag rebuilt is different bytes.
- Measurement conditions are part of the record, not commentary: host specification, CPU and
  memory limits, whether the database was already healthy, repetition count, and which run was
  discarded as warm-up.
- Timings are reported as median and p90 over at least ten runs. Never a mean.
