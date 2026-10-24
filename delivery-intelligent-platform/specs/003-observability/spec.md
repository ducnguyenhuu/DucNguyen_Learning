# Feature Specification: Observability

> **Historical — multi-tenancy was removed on 2026-10-23** ([ADR-025](../../docs/adr/ADR-025-single-organization.md)). This spec describes the system as built at the time and is not rewritten. Where it says tenant, the current code has one organization per deployment, and the service is `src/Identity`. `tenant.id` enrichment no longer exists; spans and logs carry `user.id`.

**Feature Branch**: `003-observability`
**Created**: 2026-08-22
**Status**: Draft
**Input**: User description: "S4 — Observability. Per roadmap.md: OpenTelemetry traces/metrics/logs, OTel Collector exporting to New Relic (ADR-018, over OTLP), correlation ID propagated across every boundary, tenant + user enrichment on spans and logs only (never as a metric dimension, per New Relic's per-day cardinality limit), health checks (self + dependencies), immutable audit log, sampling/drop rules, local collector for offline work. Not in scope: App Insights as secondary exporter (optional, S6), dashboards, alerting, SLOs, New Relic APM agent (never — OTLP only per ADR-011/ADR-018)."

## Clarifications

### Session 2026-08-22

- Q: What sampling strategy and rate applies to successful-request traces? → A: Tail-based sampling — retain 100% of error traces, sample a low, configurable rate (default 10%) of successful traces, decided after the trace completes.
- Q: How long is an audit entry retained? → A: Indefinitely — no deletion or archival mechanism in this slice; a retention/archival policy is deferred until a specific compliance requirement demands one.
- Q: What is the health-check interval referenced in SC-004? → A: 30 seconds — a common default for readiness/liveness probes, fast enough to detect an outage without over-polling dependencies.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose a failure from telemetry alone (Priority: P1)

An operator investigating a reported problem (a failed request, a slow response, an
unexpected error) can reconstruct exactly what happened — which request, which tenant,
which internal calls, in what order, with what timing — by reading traces and logs,
without asking the reporting user for more detail and without reproducing the issue
locally.

**Why this priority**: This is the whole point of the slice. Constitution Principle VI
requires a failure to be diagnosable from telemetry alone. Every other story in this
slice exists to make this one true.

**Independent Test**: Trigger a request that fails partway through (e.g. an invalid
tenant context), then find its full server-side story using only its correlation
identifier — one trace showing every internal step, and structured log lines that
carry the same identifier.

**Acceptance Scenarios**:

1. **Given** an incoming request, **When** it is processed, **Then** a single
   correlation identifier is generated (or propagated, if the caller supplied one) and
   present on every span and every structured log line produced while handling it.
2. **Given** a request that fails, **When** an operator looks up its correlation
   identifier, **Then** they can see the full sequence of internal operations that ran,
   with enough detail (operation name, timing, tenant, outcome) to identify where it
   failed, without reading application source code to interpret the trace.
3. **Given** a request that succeeds normally, **When** its trace is inspected,
   **Then** it carries the same structural detail as a failed one (this is not a
   failure-only feature — the trace format doesn't change based on outcome).

---

### User Story 2 - Know a service is healthy without asking a human (Priority: P1)

An operator or automated system can ask a running service "are you healthy?" and get an
answer that reflects both the service's own state and the state of what it depends on
(database, downstream services), without needing to inspect logs or traces to find out.

**Why this priority**: Health checks are the cheapest, fastest signal for automated
recovery and deployment gating, and every other observability signal in this slice
assumes the service reporting them is itself known to be up. This is foundational
alongside Story 1, not sequential to it.

**Independent Test**: Query a running service's health endpoint with a dependency
(e.g. the database) unavailable, and confirm the response reflects the unhealthy
dependency rather than reporting healthy because the process itself is still running.

**Acceptance Scenarios**:

1. **Given** a running service with all dependencies available, **When** its health
   endpoint is queried, **Then** it reports healthy.
2. **Given** a running service whose database is unreachable, **When** its health
   endpoint is queried, **Then** it reports unhealthy, identifying which dependency
   failed.
3. **Given** a service that is still starting up (e.g. running migrations), **When**
   its health endpoint is queried, **Then** it reports a distinct "not ready yet" state
   rather than either "healthy" or an opaque failure.

---

### User Story 3 - Prove a security- or tenant-relevant action happened, unforgeable (Priority: P2)

A tenant administrator or auditor can retrieve a permanent, tamper-evident record of
security-relevant and tenant-mutating actions (who did what, to what, when) that cannot
be altered or deleted by ordinary application code after the fact — separate from
general-purpose application logs, which are retained for operational diagnosis only
and are not tamper-evident.

**Why this priority**: This is a compliance and trust requirement, not a debugging
tool — it matters for after-the-fact investigation and dispute resolution, not for
day-to-day operations, so it is valuable but not on the critical path the other two
stories are.

**Independent Test**: Perform a tenant-mutating action (e.g. remove a member), then
confirm a corresponding audit entry exists, is retrievable, and that no code path in
the application exposes a way to modify or delete it.

**Acceptance Scenarios**:

1. **Given** a tenant-mutating action (membership change, role change, invitation,
   tenant settings change), **When** it completes, **Then** an audit entry recording
   who did it, to what, and when, is durably persisted.
2. **Given** an audit entry has been written, **When** any application code attempts
   to modify or delete it, **Then** no such operation exists to attempt — the audit
   store is append-only by construction, not by convention.
3. **Given** an authentication or authorization refusal (already logged per spec
   001's FR-025), **When** it is security-relevant, **Then** it is also captured in the
   audit trail, not only in general application logs.

---

### User Story 4 - Work with telemetry offline, without an external dependency (Priority: P3)

A developer working without connectivity to the external telemetry backend can still
run the system locally and see traces, metrics, and logs, using a local collector
instead of the hosted backend.

**Why this priority**: This is a developer-experience and cost-control convenience — it
removes a hard dependency on an external, paid service for local work — but nothing
else in this slice depends on it, and it is not required for the slice's core
diagnosability goal.

**Independent Test**: Run the system with network access to the external telemetry
backend blocked, and confirm traces/metrics/logs are still visible via a local
collector.

**Acceptance Scenarios**:

1. **Given** the external telemetry backend is unreachable, **When** the system runs
   locally, **Then** a local collector still receives and can display traces, metrics,
   and logs.
2. **Given** a developer switches from local-only to backend-connected operation,
   **When** they do so, **Then** no code change is required — only configuration
   (the exporter target), since instrumentation is vendor-neutral by construction
   (ADR-011).

---

### Edge Cases

- What happens when the telemetry backend itself is unreachable at runtime (not a
  local-collector scenario, but the hosted backend failing while the system is live)?
  The application MUST continue serving requests — telemetry export failures must never
  cause a request to fail or block.
- What happens when a request arrives with a caller-supplied correlation identifier
  that is malformed or not in the expected propagation format? The system generates a
  fresh, valid identifier rather than propagating or rejecting the malformed one.
- What happens when sampling drops a trace that would have shown a failure? The
  sampling/drop rules MUST bias toward keeping error traces (a failed request is never
  sampled away), even if a fraction of successful traces are dropped for volume control.
- What happens to tenant/user identity enrichment when the caller is unauthenticated
  (e.g. a request rejected before tenant resolution)? Spans and logs still get whatever
  identity is known at that point (none, in this case) — enrichment happens with
  whatever context exists, it does not block or fail when context is incomplete.
- What happens when the audit log's storage itself is temporarily unavailable? A
  tenant-mutating action that cannot be durably audited MUST NOT be treated as having
  succeeded — the action and its audit record are written together, not as two
  independent, best-effort steps.

## Requirements *(mandatory)*

### Functional Requirements

**Tracing, metrics, and logs (adopts ADR-011, ADR-018)**

- **FR-001**: Every incoming request MUST have a correlation identifier: propagated
  from the caller if present and valid, generated fresh otherwise. The identifier MUST
  be attached to every trace span and every structured log line produced while
  handling that request, and MUST use the W3C Trace Context propagation format across
  service boundaries.
- **FR-002**: Every service-to-service and asynchronous-messaging boundary MUST
  propagate the correlation identifier, so a single logical operation spanning multiple
  hops remains traceable as one connected trace, not several disconnected ones.
- **FR-003**: All traces, metrics, and logs MUST be produced via the OpenTelemetry
  API/SDK, exported over OTLP. No vendor-specific instrumentation SDK or agent may be
  used for telemetry (ADR-011, ADR-018).
- **FR-004**: Traces and logs MUST be enriched with tenant identity and user identity
  when known at the point of emission. Metrics MUST NOT carry tenant identity or user
  identity as a dimension (New Relic's per-metric-name, per-day cardinality limit
  applies to metrics only) — a per-tenant metric need, if any, MUST use a bounded
  proxy (e.g. tier or shard), never raw tenant identity.
- **FR-005**: Telemetry MUST NOT include secrets, credentials, or unnecessary personal
  data (Constitution Principle XI) — the same discipline spec 001's FR-025 already
  established for application logs extends to traces and metrics.
- **FR-006**: A telemetry export failure or backend unavailability MUST NOT cause a
  request to fail, block, or slow down beyond a bounded, small overhead — telemetry
  emission is fire-and-forget from the request's perspective.
- **FR-007**: Trace sampling MUST be tail-based: the decision to retain or drop a
  trace is made after the trace completes, not before. Every trace for a
  failed/errored request MUST be retained (100%, no exceptions). Successful-request
  traces MUST be sampled at a low, configurable rate, defaulting to 10%.

**Health checks**

- **FR-008**: Every service MUST expose a health-check surface reporting at least three
  distinct states: healthy, unhealthy (with the specific failing dependency identified),
  and not-yet-ready (for startup/initialization).
- **FR-009**: A service's health status MUST reflect the reachability of its direct
  runtime dependencies (at minimum, its own database), not merely that its own process
  is running.

**Immutable audit log**

- **FR-010**: Every tenant-mutating action (membership create/remove/role-change,
  invitation issue/accept/revoke, tenant settings change) and every security-relevant
  authorization refusal MUST produce a durable audit entry recording the actor, the
  action, the affected resource, and the time it occurred.
- **FR-011**: The audit store MUST be append-only: no code path in the application may
  update or delete an existing audit entry. This must be a structural property of the
  store's own access surface, not a convention application code chooses to follow.
- **FR-012**: A tenant-mutating action and its audit entry MUST be written as a single
  durable unit — an action MUST NOT be considered complete if its audit entry failed to
  persist.
- **FR-013**: The audit log is a separate concern from general application logging
  (spec 001 FR-025): general logs remain retained for operational diagnosis and are not
  required to be tamper-evident; only the audit log carries the append-only guarantee.
- **FR-013a**: Audit entries are retained indefinitely in this slice — no deletion or
  archival mechanism is implemented. A retention/archival policy is explicitly deferred
  until a concrete compliance requirement defines one.

**Local development**

- **FR-014**: A local OpenTelemetry Collector configuration MUST exist so the system
  can run and display traces/metrics/logs without connectivity to the hosted backend.
  Switching between local-only and backend-connected operation MUST require only
  exporter configuration, never an application code change.

### Key Entities

- **Trace / Span**: A single logical operation's timeline, and the individual steps
  within it, carrying the correlation identifier and (when known) tenant/user identity.
- **Correlation Identifier**: A unique value generated at the entry point of a request
  (or propagated from an upstream caller), present on every span and log line produced
  while handling that request, in W3C Trace Context format across boundaries.
- **Health Check Result**: A service's self-reported state (healthy / unhealthy /
  not-ready), naming the specific dependency responsible for an unhealthy verdict.
- **Audit Entry**: An append-only record of a tenant-mutating action or a
  security-relevant authorization refusal — actor, action, affected resource, timestamp
  — durably persisted in the same unit of work as the action it records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can reconstruct the full server-side sequence of a failed
  request using only its correlation identifier, with no source-code reading and no
  local reproduction required.
- **SC-002**: 100% of requests that touch more than one service boundary produce a
  single connected trace spanning every hop, not multiple disconnected traces.
- **SC-003**: Zero telemetry attributes across the system's metrics carry raw tenant or
  user identity as a dimension.
- **SC-004**: A dependency outage (e.g. database unreachable) is reflected in a
  service's health status within 30 seconds (one health-check interval), without any
  request to the application's business endpoints being required to detect it.
- **SC-005**: 100% of tenant-mutating actions produce a corresponding, durable audit
  entry; zero audit entries can be modified or deleted through any application code
  path.
- **SC-006**: The system's telemetry and audit behavior are identical whether the
  telemetry backend is the hosted service or a local collector — no code change, only
  configuration, is needed to switch between them.
- **SC-007**: An external telemetry backend outage causes zero application request
  failures attributable to telemetry emission.
