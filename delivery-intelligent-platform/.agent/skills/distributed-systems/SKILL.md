---
name: distributed-systems
description: Use when working with Service Bus, background jobs, sync engines, or any cross-service call — covers messaging, idempotency, retries, eventual consistency, and failure handling.
---

# Distributed Systems

`idea.md` §21 lists these as mandatory, not optional: timeout, retry, idempotency,
circuit breaker, dead-letter queues, duplicate messages, eventual consistency,
correlation IDs. Constitution Principle VII requires them tested, not just present.

They are mandatory because ADR-003 chose service boundaries with exclusive data
ownership — which makes eventual consistency a permanent property of the system rather
than an edge case.

## The rules

**1. Every message handler is idempotent.**

Service Bus guarantees *at-least-once*, not exactly-once. Duplicates are normal
operation, not a fault. Keep a deduplication store keyed by message ID and check it
before doing work.

```csharp
if (await _dedupe.AlreadyProcessed(message.MessageId, ct)) return;   // not an error
await Handle(message, ct);
await _dedupe.MarkProcessed(message.MessageId, ct);
```

**2. Never dual-write. Use the outbox pattern.**

Writing to the database and publishing to Service Bus are not one atomic operation. If the
publish fails after the commit, the event is lost silently — the worst kind of bug,
because nothing reports it.

Write the event to an outbox table **in the same transaction** as the state change, then
publish from the outbox in a background dispatcher.

**3. Retry with exponential backoff and jitter.** Bounded attempts. Retrying forever is
how you turn a downstream blip into an outage.

**4. Dead-letter, and build the replay tooling.** A DLQ you cannot inspect and replay is a
place where messages go to be forgotten. Slice 8's proof requires an actual replay.

**5. Propagate the correlation ID through the message body or properties.** The trace must
survive the hop, otherwise `idea.md` §20's unbroken trace across Service Bus is
impossible. See the `observability` guidance in ADR-011.

**6. Every external call has a timeout.** No exceptions. A missing timeout is a hang
waiting to happen.

**7. Circuit breakers on external dependencies.** Especially the Jira/ADO connector at
slice 9 — a rate-limited or down external API must not cascade.

## Eventual consistency

Cross-service invariants tolerate staleness. Design for it explicitly:

- Never assume another service's data is current
- Surface freshness to the user rather than hiding it (slice 11 requires this)
- No distributed transactions, no two-phase commit
- If an invariant genuinely cannot tolerate staleness, it belongs inside **one**
  aggregate — which may mean the boundary is wrong (Principle II: propose moving it)

## Background jobs — the dangerous ones

A background job has no request, so **no caller, no request scope, and no correlation ID**
unless it creates them. A hosted service is a singleton, so a `DbContext` or repository
taken in its constructor is a captive dependency shared across every execution — stale
and not thread-safe. `BackgroundJobGates` blocks that shape.

Every background job must:

- Create a DI scope per unit of work (`IServiceScopeFactory`) and resolve scoped services
  inside it
- Never read `ICallerContext` — there is no caller; pass the acting identity explicitly if
  one matters
- Continue the trace from the message it is processing, so telemetry stays correlated

## Slice 8 scope — deliberately one event

`MemberInvited`, and nothing more. The point is the failure handling, not the number of
events.

Chosen because every event in `idea.md` §16 depends on delivery data that does not exist
until slice 11 — so an Identity event is the only kind available in Horizon 1. The S8 event
was `TenantCreated` until multi-tenancy was removed (ADR-025). It is not in §16's list; see
[U5](../../../docs/traceability.md#u5--16s-event-list-does-not-contain-the-event-roadmap-s8-builds).

Not in scope: additional events, sagas, orchestration, event sourcing, schema registry.

## The research-first bar

`idea.md` §59.2: **Service Bus is not learned until a duplicate has been handled
idempotently and a dead letter has been replayed.**

Slice 8's proof requires both, demonstrated. Publishing one message and seeing it arrive
is the happy path, and the happy path teaches you nothing about messaging.

## Rationalizations that mean you're about to lose or duplicate a message

| Thought | Reality |
|---------|---------|
| "Service Bus rarely redelivers in practice" | Rarely is not never, and "at-least-once" is the documented contract, not a corner case. A handler that isn't idempotent will double-process eventually. |
| "I'll publish right after the commit, that's basically atomic" | It's two separate operations. The commit can succeed and the publish can fail — silently, with nothing reporting it. That's exactly what the outbox pattern exists to close. |
| "Retrying forever is safer than giving up" | Retrying forever turns a five-minute downstream blip into a permanent backlog or an outage. Bound it and dead-letter instead. |
| "We don't need to inspect the DLQ, nothing's landed there yet" | A DLQ with no replay tooling is where messages go to be forgotten the first time something does land. Build it before you need it, not after. |
| "I'll inject the DbContext into the hosted service's constructor, it's simpler" | A hosted service is a singleton, so that DbContext lives forever and is shared across executions. Create a scope per unit of work. |
| "One message published and received — messaging is proven" | The happy path teaches nothing about failure handling. The bar here is a duplicate handled idempotently and a dead letter replayed, both demonstrated. |

## Red flags — stop and re-check

- A handler with no dedupe check before doing work
- A publish call with no corresponding outbox write in the same transaction
- A retry loop with no bounded attempt count
- A DLQ nobody has ever inspected or replayed from
- A background job or event handler that takes a DbContext or repository in its constructor
- A correlation ID that stops at the messaging boundary instead of riding in the message body or properties

**All of these mean: stop, and don't call the integration done until a duplicate and a dead letter have actually been exercised.**

## Anti-patterns

- Assuming exactly-once delivery
- Dual-writing to database and broker
- Unbounded retries
- Swallowing a handler exception, so the message is lost silently
- A DLQ with no inspection or replay path
- Breaking the trace at the messaging boundary
- Background jobs holding scoped services captive
