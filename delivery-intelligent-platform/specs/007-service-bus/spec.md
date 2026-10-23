# Feature Specification: Service Bus Messaging with Failure Handling

**Feature Branch**: `007-service-bus`  
**Created**: 2026-10-23  
**Status**: Draft  
**Input**: User description: "start S8 spec". Per roadmap.md S8: Service Bus via Terraform · `TenantCreated` end to end · publisher using the outbox pattern (no dual-write) · idempotent subscriber with a dedupe store · retry with backoff · circuit breaker · DLQ + own replay tooling · correlation ID carried through the message. Not: more events · sagas · event sourcing · schema registry. Runs locally against the Service Bus emulator because no Azure budget is available until next month; the Terraform is written and validated but applied only in the paid S6/S7 session.

## Clarifications

### Session 2026-10-23

- Q: What does the subscriber do with `TenantCreated`, and which service owns it? → A: A
  background subscriber inside the Tenancy service records a per-tenant setup record in
  Tenancy's own database. No new service is created. The message does not cross a service
  boundary in this slice; cross-service consumers arrive with later slices.
- Q: Does S8 count as done on emulator evidence alone? → A: No. S8 stays 🟡 until the Terraform
  is applied and the proofs are re-run against Azure Service Bus in the paid session, the same
  convention as S6 and S7.

## User Scenarios & Testing *(mandatory)*

This slice exists to prove messaging **failure handling**, not to deliver many events
(idea.md §59.2: "Service Bus without duplicate delivery and a dead-letter replay is not
learning Service Bus"). One event, `TenantCreated`, is enough. Several stories are
therefore failure scenarios rather than features.

### User Story 1 - A created tenant is announced reliably (Priority: P1)

As the platform, when a user creates a tenant, I announce `TenantCreated` to other parts of
the system exactly once in effect, so downstream work can react without the tenant service
calling it directly.

**Why this priority**: Every later story needs one event flowing end to end. Without it,
there is nothing to duplicate, fail, or replay.

**Independent Test**: Create a tenant through the existing API with the local stack running,
then confirm a tenant setup record exists for that tenant, and that one trace covers the whole
path.

**Acceptance Scenarios**:

1. **Given** the local stack with the message broker running, **When** a user creates a tenant,
   **Then** the subscriber records its effect for that tenant within 30 seconds.
2. **Given** a tenant was created, **When** the trace for the creating request is inspected,
   **Then** one trace spans the HTTP request, the publish, the broker, the subscriber, and the
   subscriber's database write, all carrying the original correlation ID.
3. **Given** tenant creation is rejected (validation failure, or an idempotent repeat of an
   earlier request under spec 001 FR-020), **When** the request completes, **Then** no new
   `TenantCreated` event is published.

---

### User Story 2 - A duplicated message has no double effect (Priority: P1)

As the platform, when the same `TenantCreated` message is delivered more than once, I apply
its effect only once, because at-least-once delivery guarantees duplicates will happen.

**Why this priority**: This is a Gate 1 box. Duplicate delivery is the normal case for
at-least-once messaging, not an edge case.

**Independent Test**: Deliver the same message twice (re-send it, or let a delivery fail after
the effect was applied so the broker redelivers), then confirm exactly one effect exists and
the second delivery is recorded as a recognised duplicate.

**Acceptance Scenarios**:

1. **Given** a `TenantCreated` message was processed, **When** the identical message is
   delivered again, **Then** no second effect is recorded and the duplicate is completed, not
   retried or dead-lettered.
2. **Given** the subscriber applied the effect but crashed before acknowledging, **When** the
   broker redelivers the message, **Then** the effect is still recorded exactly once.
3. **Given** two copies of the same message are delivered concurrently to two subscriber
   instances, **When** both are processed, **Then** exactly one effect is recorded.

---

### User Story 3 - The event survives a failure after the tenant is saved (Priority: P1)

As the platform, if the broker is unreachable when a tenant is created, the tenant still
exists and its `TenantCreated` event is delivered once the broker recovers, so a saved tenant
is never silently left unannounced and an announced tenant is never missing.

**Why this priority**: Saving the tenant and sending the message separately (dual-write) loses
or invents events on partial failure. Proving the event is stored with the tenant and sent
later is the core of the publisher design.

**Independent Test**: Stop the broker, create a tenant, confirm the API call succeeds and the
event is waiting unsent, restart the broker, then confirm the event is delivered and the
subscriber's effect appears.

**Acceptance Scenarios**:

1. **Given** the broker is unreachable, **When** a user creates a tenant, **Then** the request
   succeeds and the event is stored as pending in the same commit as the tenant.
2. **Given** a pending event exists, **When** the broker becomes reachable, **Then** the event
   is published within 60 seconds and marked as sent.
3. **Given** the tenant's database commit fails, **When** the request completes, **Then** no
   event is stored or published.
4. **Given** the publisher crashes after sending but before marking the event as sent, **When**
   it restarts, **Then** it may send the event again, and User Story 2 ensures no double effect.

---

### User Story 4 - A failing message is retried, then dead-lettered and replayed (Priority: P2)

As an operator, when a message cannot be processed, the system retries it with increasing
delays and then moves it to a dead-letter queue. I can inspect and replay it with the
project's own tooling once the cause is fixed.

**Why this priority**: This is a Gate 1 box. Retry and dead-lettering are only learned when a
real message fails, and replay is only learned when one is brought back.

**Independent Test**: Make the subscriber's processing fail for a chosen tenant, observe
retries with growing delays, confirm the message lands in the dead-letter queue with its
failure reason, remove the cause, replay with the tooling, and confirm the effect is recorded
once.

**Acceptance Scenarios**:

1. **Given** processing fails with a transient error, **When** the message is delivered,
   **Then** it is retried with increasing delays and succeeds once the error clears, with no
   operator action.
2. **Given** processing keeps failing, **When** the maximum delivery count is reached,
   **Then** the message is moved to the dead-letter queue with the failure reason and its
   correlation ID intact.
3. **Given** a message that can never succeed (for example malformed or of an unknown
   version), **When** it is delivered, **Then** it is dead-lettered immediately without
   exhausting retries.
4. **Given** a dead-lettered message and the cause fixed, **When** an operator replays it with
   the project's tooling, **Then** it is processed, its effect is recorded exactly once, and
   the replay is attributable (who replayed what, and when).
5. **Given** the operator lists the dead-letter queue, **When** the tooling runs, **Then** each
   message shows its identifier, tenant, failure reason, delivery count, and correlation ID,
   without exposing message content beyond those fields.

---

### User Story 5 - Sustained failure trips a circuit breaker, then recovers (Priority: P3)

As the platform, when a dependency stays down, I stop calling it for a while instead of
hammering it, and I resume on my own when it comes back.

**Why this priority**: The roadmap requires it, but it builds on Stories 3 and 4 and protects
the system rather than proving delivery.

**Independent Test**: Keep the guarded dependency unavailable, confirm the breaker opens and
calls stop, restore the dependency, and confirm the breaker closes and pending work drains
without an operator.

**Acceptance Scenarios**:

1. **Given** the guarded dependency fails repeatedly, **When** the failure threshold is
   crossed, **Then** the breaker opens, calls stop for the open period, and the transition is
   visible in telemetry.
2. **Given** the breaker is open and the dependency recovers, **When** the open period ends,
   **Then** a trial call succeeds, the breaker closes, and pending work drains.
3. **Given** the breaker is open, **When** a user creates a tenant, **Then** the request still
   succeeds and its event waits as pending (User Story 3).

### Edge Cases

- A message with no tenant identifier, or one naming a tenant that does not exist, is
  dead-lettered with a clear reason. It is never processed under an unset or guessed tenant
  context.
- A message whose correlation ID is missing is processed under a new correlation ID, and the
  gap is logged rather than failing the message.
- A duplicate arrives after its dedupe record has expired. The retention window must exceed
  the longest realistic redelivery or replay delay (see Assumptions).
- An operator replays the same dead-lettered message twice. The second replay has no effect
  (User Story 2).
- The subscriber is shut down mid-message. The message is not acknowledged and is redelivered,
  and the effect is still recorded once.
- Pending events build up during a long broker outage. When the broker returns, they are sent
  oldest first, and events for the same tenant are not reordered.
- The broker or its local emulator is not running when the stack starts. Tenant operations
  stay available, and the readiness report shows messaging as degraded rather than failing the
  whole service.

## Requirements *(mandatory)*

### Functional Requirements

**Publishing**

- **FR-001**: Creating a tenant MUST store a `TenantCreated` event in the same atomic commit as
  the tenant. Publishing directly to the broker inside the request (dual-write) is prohibited.
- **FR-002**: A background publisher MUST deliver stored events to the broker and mark each as
  sent only after the broker accepts it. Unsent events MUST survive a process restart.
- **FR-003**: An event MUST carry a stable unique message identifier, the event type and schema
  version, the tenant identifier, the time of occurrence, and the correlation ID of the
  originating request. It MUST NOT carry secrets, credentials, or personal data beyond what the
  subscriber needs.
- **FR-004**: A rejected or repeated tenant-creation request (spec 001 FR-020) MUST NOT produce
  an additional event.

**Consuming**

- **FR-005**: The subscriber MUST apply the effect of `TenantCreated` exactly once per message
  identifier, using a durable record of processed identifiers. A duplicate MUST be completed
  without re-applying the effect, and recording the identifier MUST be atomic with the effect.
- **FR-006**: The subscriber MUST establish tenant context from the message before touching
  tenant-scoped data. It MUST refuse (dead-letter) a message without a valid tenant, and it
  MUST pass the existing S3 architecture rule that background work sets tenant context.
- **FR-007**: The subscriber MUST be a background component of the Tenancy service. Its effect
  MUST be a tenant setup record in Tenancy's own database, recording the tenant, the message
  identifier that produced it, and when setup completed. It MUST NOT read or write another
  service's data store (Principle III). It MUST receive the event only through the broker,
  never by an in-process shortcut.

**Failure handling**

- **FR-008**: Transient processing failures MUST be retried with increasing delays, up to a
  configured maximum delivery count. After that, the message MUST be dead-lettered with its
  failure reason.
- **FR-009**: Permanent failures (malformed message, unknown schema version, missing tenant)
  MUST be dead-lettered on first delivery without exhausting retries.
- **FR-010**: The project MUST provide its own operator tooling to list, inspect, and replay
  dead-lettered messages. Replay MUST require an explicit operator action naming the message
  or messages. Each replay MUST be recorded (operator, message identifier, time, outcome) in
  the existing immutable audit log, and the tooling MUST be unavailable to tenant users.
- **FR-011**: A circuit breaker MUST guard the publisher's calls to the broker. It MUST open
  after sustained failure, stop calling for a configured period, close on a successful trial,
  and emit telemetry on each state change.

**Observability**

- **FR-012**: The correlation ID MUST travel inside the message, so one trace connects the HTTP
  request, the stored event, the publish, the broker hop, the subscriber, and the subscriber's
  database write.
- **FR-013**: Retries, duplicates detected, dead-letterings, replays, and breaker transitions
  MUST each be visible in telemetry with tenant and correlation ID on spans and logs only. They
  MUST NOT be metric dimensions (ADR-018 cardinality rule).
- **FR-014**: The service's readiness report MUST include the broker as a dependency without
  making tenant operations unavailable while the broker is down (consistent with S5 FR-006).

**Environment and decision record**

- **FR-015**: The local composed stack MUST include the broker (the Service Bus emulator) so
  every story runs on a developer machine with no Azure subscription.
- **FR-016**: The broker namespace, queue or topic and subscription, dead-letter settings, and
  the service's access through managed identity (no connection-string secret, Principle V) MUST
  be defined in Terraform and pass `terraform validate`. Applying it is deferred to the paid
  S6/S7 session.
- **FR-017**: ADR-005 (Azure Service Bus) MUST be written in this slice. It records the
  delivery guarantees, the outbox and dedupe choices, the retry, dead-letter and breaker
  settings, and the known differences between the emulator and Azure.
- **FR-018**: Every story above MUST be proven by an automated test that runs unattended
  against the local broker, including the failure scenarios in Stories 2–5.

### Key Entities

- **Stored event (outbox entry)**: an event saved with the tenant in one commit. It holds the
  message identifier, type, schema version, tenant, payload, correlation ID, created time, sent
  time (empty until delivered), and attempt count. It is owned by the Tenancy service.
- **`TenantCreated` message**: the published form of the stored event. It carries the fields in
  FR-003.
- **Processed-message record (dedupe store)**: the message identifiers the subscriber has
  already applied, with the time processed. It is owned by the Tenancy service and kept for the
  retention window.
- **Tenant setup record**: the subscriber's effect, holding the tenant, the message identifier
  that produced it, and the completion time. There is at most one per tenant. It is owned by the
  Tenancy service.
- **Dead-lettered message**: a message the broker set aside. It keeps its original content,
  failure reason, delivery count, and correlation ID until replayed or purged.
- **Replay record**: an audit entry for each replay, holding the operator, message identifier,
  time, and outcome.

### Assumptions

- **Local first.** No Azure budget is available until next month. Every story is proven
  against the Service Bus emulator in the local stack. Applying the FR-016 Terraform and
  repeating the proofs in Azure happen in the same paid session that completes S6 and S7.
  Until that re-run, S8 is 🟡 in roadmap.md, not ✅ (Clarifications, Q2).
- **Emulator differences** found during the slice are recorded in ADR-005 (FR-017). Each one
  becomes a check in the Azure re-run.
- **Retry defaults**, adjustable in planning: up to 5 deliveries with exponential backoff
  starting at about 2 seconds, then dead-letter.
- **Dedupe retention**: at least 7 days, longer than any expected redelivery or manual replay
  delay. An operator replaying something older than that window is a documented limitation.
- **Ordering**: no global ordering is promised. Only the one-event-per-tenant case must not be
  reordered for the same tenant.
- **Breaker placement**: the breaker guards the publisher-to-broker path, because that is the
  dependency that can stay down for long stretches. A breaker on the subscriber's own database
  is not required.
- **Tooling form**: replay tooling is an operator command run with operator credentials, not
  an HTTP endpoint in the tenant API. That keeps it outside the tenant-facing attack surface.
- **One instance by default.** Concurrency (Story 2 scenario 3) is proven in tests by running
  two subscriber instances, not by production scale-out.

### Out of Scope

- Any event other than `TenantCreated` (including the later `Member*` events in the domain
  model).
- Sagas, process managers, event sourcing, a schema registry, or broker sessions for strict
  ordering.
- Publishing from services other than Tenancy, any consumer outside the Tenancy service, or the
  Horizon 2 consumers in idea.md §16 (AI, Analytics, Notification).
- Applying the Terraform, Azure-side verification, and pipeline changes to deploy messaging.
  Those happen in the paid session alongside S6 and S7.
- Dashboards, alerting, and SLOs for messaging (as in S4).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 20 consecutive local runs, every created tenant has its subscriber effect
  recorded within 30 seconds, with zero missing and zero doubled effects.
- **SC-002**: Across at least 100 deliberately duplicated deliveries (sequential, concurrent,
  and crash-before-acknowledge), 100% produce exactly one effect.
- **SC-003**: With the broker stopped for at least 5 minutes while tenants are created, 100% of
  creation requests succeed and 100% of their events are delivered within 60 seconds of the
  broker returning.
- **SC-004**: A dead-lettered message is found, inspected, and replayed by someone following
  only the documented procedure in under 10 minutes, and the replay appears in the audit log.
- **SC-005**: For a single tenant creation, one trace with one correlation ID covers all six
  hops in FR-012, as seen in the telemetry backend.
- **SC-006**: During a sustained broker outage, the publisher's broker calls drop to no more
  than one trial call per open period, and the breaker closes within one open period of the
  broker returning.
- **SC-007**: The full S8 test suite, including every failure scenario, runs unattended and
  keeps the whole suite within the S3 five-minute budget.
