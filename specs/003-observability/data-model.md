# Data Model: Observability

This slice adds one new persisted entity (`AuditEntry`) and one new value shape
(`HealthCheckResult`, not persisted — computed per request). Traces, spans, and
metrics are OpenTelemetry SDK concepts, not entities this codebase defines.

## AuditEntry

Lives in `Tenancy.Domain.Auditing`. Append-only (see research.md R2 — enforced by a
database trigger, not application code).

| Field | Type | Notes |
|---|---|---|
| `Id` | `AuditEntryId` (strongly-typed, `Guid`-backed, per this codebase's established ID convention) | Primary key |
| `TenantId` | `TenantId?` | Nullable — an authentication refusal may occur before tenant context resolves (per spec's edge cases); null means "no tenant context was established yet," not "unknown" |
| `ActorUserId` | `UserId?` | Nullable for the same reason — an unauthenticated refusal has no resolved user |
| `Action` | `string` | A short, stable action identifier (e.g. `"membership.removed"`, `"invitation.revoked"`, `"authorization.refused"`) — not a free-text description |
| `ResourceType` | `string` | What kind of thing was acted on (e.g. `"Membership"`, `"Invitation"`, `"Tenant"`) |
| `ResourceId` | `string` | The affected resource's identifier, as a string (the various resource ID types don't share a common base type, so this is stored as its string form) |
| `OccurredAtUtc` | `DateTimeOffset` | Set from the injected `IClock` (this codebase's existing testable-time abstraction), never `DateTimeOffset.UtcNow` directly |

**Validation rules**:
- `Action`, `ResourceType`, `ResourceId` are required, non-empty.
- `TenantId` and `ActorUserId` may both be null (unauthenticated refusal case) but if
  one is set without the other in a case that should logically have both, that's an
  application-layer bug to catch in tests, not a constraint the entity itself can
  express (the entity permits the state; specific call sites are responsible for
  populating what they actually know).

**Relationships**: None to other aggregates by foreign key — `TenantId`/`ActorUserId`/
`ResourceId` are held as values (per this codebase's cross-context reference
convention, e.g. `ITenantRepository`'s existing "hold an ID, don't join" pattern), not
navigation properties. An audit entry must remain readable even if the tenant or user
it references is later deleted (not that deletion exists yet in this codebase, but the
entity should not assume it never will).

**Lifecycle**: Created once, at the same time as the action it records (research.md
R5). Never updated. Never deleted (FR-013a — indefinite retention in this slice).

## HealthCheckResult (not persisted)

A per-request computed value, shaped by the `Microsoft.Extensions.Diagnostics.HealthChecks`
middleware's own result type (`HealthReport`), not a new domain entity. Recorded here
only to state the three states FR-008 requires map onto the library's existing model:

| Spec state | Library's `HealthStatus` | Route |
|---|---|---|
| Healthy | `Healthy` | `/health/ready` (and `/health/live`) |
| Unhealthy (dependency named) | `Unhealthy` | `/health/ready`, response body names the failing check |
| Not-yet-ready | `Unhealthy` on `/health/ready` until first successful check completes, while `/health/live` already reports `Healthy` (process is up) | Distinguished by which of the two routes disagrees |

## Correlation Identifier (not persisted)

An OpenTelemetry `TraceId`/`SpanId` pair, propagated per W3C Trace Context. Not a new
type this codebase defines — it is read from `Activity.Current` (the .NET runtime's
built-in distributed-tracing primitive that OpenTelemetry's ASP.NET Core
instrumentation populates automatically) wherever a log line needs to include it.
