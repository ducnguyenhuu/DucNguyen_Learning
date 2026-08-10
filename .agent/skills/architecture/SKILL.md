---
name: architecture
description: Use when adding a service, moving a boundary, deciding where new code belongs, or checking whether a change respects service and data-ownership boundaries.
---

# Architecture

## Authority first

Before deciding anything structural, check whether it is already decided:

- [ADR-003](../../../docs/adr/ADR-003-service-oriented-architecture.md) — boundaries, data ownership
- [domain-model.md](../../../docs/architecture/domain-model.md) — contexts, aggregates
- [Constitution Principle III](../../../.specify/memory/constitution.md)

**If a recorded decision looks wrong, propose a change. Do not work around it**
(Principle II). Working around an ADR silently is the single most damaging thing you can
do in this repository, because it makes the documentation lie.

## The four contexts

| Context | Owns | Slice |
|---------|------|-------|
| Tenancy | Tenant, User, Membership, Invitation | 2 |
| Integration | Connection, SyncRun, RawPayload | 9 |
| Delivery | work projections, Risk, HealthScore | 11 |
| AI Platform | Capability, Prompt, Invocation, Cost | 13 |

**Services are created by the slice that needs them.** Do not scaffold a service in
advance — that is structure without content and it rots.

## Non-negotiable rules

1. **Each context owns its data exclusively.** No shared tables, no shared schemas, no
   reading another context's store. No exceptions.
2. **Cross-context references are values, not joins.** Hold a `TenantId`; never join to
   the Tenancy database.
3. **The domain layer depends on nothing outward.** Not on EF Core, not on Azure SDKs,
   not on ASP.NET. If the domain needs something from infrastructure, invert it.
4. **A new service needs justification** by bounded context, business ownership, data
   ownership, security boundary, scaling characteristic, or lifecycle. Technical
   possibility is not justification (`idea.md` §14).

## Layering

```
API / Endpoints        →  depends on Application
Application (use cases)→  depends on Domain
Domain                 →  depends on NOTHING
Infrastructure         →  depends on Domain (implements its interfaces)
```

Dependencies point inward. Infrastructure implements interfaces the domain declares.

## Native vs projection — the decision you will get wrong

The platform is an **intelligence layer**, not a work tracker (`idea.md` §3).

**Test:** does the platform add something the source system lacks?

- **No** → projection. Read from ingested data. Do not own it, do not let users edit it.
- **Yes** → native. We own it.

In the MVP only **three** delivery entities are native: `Risk`, `HealthScore`,
`Insight`. Everything else — Project, Epic, Sprint, Issue, Team — is a projection.

Adding a native entity that mirrors a Jira field is how this platform becomes a worse
Jira. When tempted, re-read `idea.md` §3 and the classification table in domain-model.md.

## Before proposing a structural change

1. Which ADR does this touch? Read it.
2. Does it cross a context boundary? If yes, does it need to?
3. Is this a new capability or a new *place* for an existing capability?
4. Can an architecture test enforce the result? If not, the design may be unenforceable
   (Principle VII prefers gates over vigilance).

## Rationalizations that mean you're about to violate a boundary

| Thought | Reality |
|---------|---------|
| "It's just a read, for reporting" | A read across contexts is still a join across a boundary that must not exist. Project the data into the reading context instead. |
| "It's temporary, I'll fix the boundary later" | Temporary shared-table code outlives its author. There is no "later" pass that removes working code. |
| "The ADR is clearly outdated, I'll just build around it" | Working around an ADR silently makes the documentation lie. Propose changing the ADR instead (Principle II) — that takes one PR comment, not a workaround. |
| "This is a small exception, not a new precedent" | Every shared-database violation in this codebase's history started as a small exception. The next person copies what they see, not what the ADR says. |
| "Scaffolding the service now saves time later" | A service created before it has a consumer is structure without content — it rots, and its shape is guessed wrong before real requirements exist. |
| "Users just want to edit this one field, it's easier to make it native" | If they need to edit it, they edit it in the source system. Making an ingested entity editable is how this platform becomes a worse Jira. |

## Red flags — stop and re-check against the ADR

- Writing a query that reads another context's tables, "just this once"
- Adding a service or project before a slice actually needs it
- A native entity that duplicates a field the source system already owns
- Justifying a structural choice by "it's technically possible" instead of by bounded context, ownership, or lifecycle
- Reaching for a workaround instead of opening a discussion to change the ADR

**All of these mean: stop, re-read the relevant ADR, and if it still looks wrong, propose changing it — don't code around it.**

## Anti-patterns seen in this domain

- **Shared database "just for reporting."** This is how service-oriented systems become
  distributed monoliths, and the coupling is invisible in code review.
- **A service per aggregate.** Explicitly rejected in ADR-003.
- **Duplicating an ingested entity so users can edit it.** If they need to edit it, they
  edit it in Jira.
- **Anemic domain with all logic in services.** Invariants belong on the aggregate — a
  Tenant that can lose its last administrator is a broken model, not a service bug.
