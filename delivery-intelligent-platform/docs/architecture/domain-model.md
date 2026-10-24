# Domain Model & Bounded Contexts

**Status**: Initial — covers what Horizons 1–2 need
**Date**: 2026-08-08
**Relates to**: `idea.md` §6, §14, §15, §19 · ADR-003 · ADR-025 · Constitution Principle III
**Resolves**: [traceability U8](../traceability.md#u8--6s-14-delivery-entities-vs-46as-projections-not-native-entities)

## Bounded contexts

Four contexts, each owning its data exclusively (ADR-003). They are introduced by the
slice that needs them — not created up front.

| Context | Owns | Introduced |
|---------|------|-----------|
| **Identity** | User, Membership, Invitation, Role | Slice 2 |
| **Integration** | Connection, Credential reference, Sync run, Raw payload | Slice 9 |
| **Delivery** | Canonical work data, Health score, Risk | Slices 11–12 |
| **AI Platform** | Capability, Prompt, Invocation, Cost record, Evaluation | Slice 13 |

**Engineering Intelligence is not a context in the MVP.** It is Horizon 3 Track D.

### Why Identity is separate from Delivery

Identity is a security boundary, and every other context depends on it. Keeping it
separate means the membership and role rules live in one place rather than being
re-implemented per context.

**Cross-context rule:** other contexts hold a `UserId` **value**, not a reference to the
Identity database. They never join to it. Membership is established once per request, at
the entry point.

**One organization per deployment** ([ADR-025](../adr/ADR-025-single-organization.md)).
There is no tenant to carry between contexts.

---

## The critical distinction: native vs projection

`idea.md` §6 lists 14 delivery concepts. `idea.md` §46a and §57.2 say the MVP reaches
its goal using **projections over ingested data**, not duplicated native entities.

Those two statements need reconciling, because §6 reads like a build list. It is not —
it is the domain vocabulary. This section decides what each concept actually is.

**The test:** does the platform add something the source system lacks?

- **No** → it is a **projection**. Read from ingested data. We do not own it, do not
  let users edit it, and do not become its system of record.
- **Yes** → it is **native**. We own it, and it lives in our database.

Getting this wrong in the permissive direction turns the platform into a worse Jira,
which `idea.md` §3 explicitly forbids.

### The 14 concepts classified

| §6 concept | Classification | Reasoning |
|---|---|---|
| **Project** | Projection | Jira/ADO owns it. We read it. |
| **Epic** | Projection | Source-owned work hierarchy. |
| **Feature** | Projection | Source-owned. |
| **Issue** | Projection | Source-owned. The atom of ingested data. |
| **Sprint** | Projection | Source-owned iteration. |
| **Team** | Projection | Derived from source assignment data in the MVP. |
| **Portfolio** | Not in MVP | Needs multi-project rollup. Nothing to roll up with one connector. |
| **Program** | Not in MVP | As above. |
| **Initiative** | Not in MVP | Overlaps Epic; no distinct value yet. |
| **Milestone** | Not in MVP | Only meaningful with Release, which is also deferred. |
| **Release** | Not in MVP | Requires deployment data we do not ingest until Track D. |
| **Capacity** | Not in MVP | Requires reliable estimate and availability data that real Jira usually lacks — validate in slice 9 before committing. |
| **Dependency** | **Native** (deferred to Horizon 3) | Cross-project dependency inference is real added value, but needs ≥2 connected projects. |
| **Risk** | **Native** ✅ | **The one clearly native concept in the MVP.** Jira has no first-class risk object with evidence, contributing factors, and forecast. This is what the platform adds. |

**Also native, and not in §6's list:**

| Concept | Reasoning |
|---|---|
| **HealthScore** | Computed by us, deterministically (slice 12). Reproducible and auditable. |
| **Insight** | The AI-generated explanation of a HealthScore (slice 14), with its grounding. |

So the MVP owns **three** delivery entities — Risk, HealthScore, Insight — and projects
everything else. That is the whole point: the platform is an intelligence layer, not a
work tracker.

---

## Identity context (slice 2)

Specified by
[specs/001-auth-tenant-management](../../specs/001-auth-tenant-management/spec.md), as
amended by [ADR-025](../adr/ADR-025-single-organization.md), which removed tenants.

### Aggregates

The organization itself is implicit: there is exactly one per deployment, and it has no
entity, name or settings of its own.

**User** *(aggregate root)* — a person or a named application identity (ADR-022).

- Identity: stable external identifier from Entra ID, the `(tid, oid)` pair
- Email
- Provisioned just-in-time on first authenticated request

**Membership** *(aggregate root)* — grants one User one Role in the organization.

- The unit that grants and revokes access, so it is the object authorization reads
- Exactly one Role; at most one active Membership per User
- Never hard-deleted: removal is a status change, so who lost access and when stays visible
- Invariant: **the organization always has at least one active Administrator**, enforced
  under a lock because two administrators may change membership concurrently
- The first Administrator bootstraps (`POST /members/bootstrap`) while no Membership exists

**Invitation** *(aggregate root)* — a pending offer of Membership to an email address.

- Intended Role, expiry (7 days), status: pending / accepted / revoked / expired
- Accepting it creates a Membership; the Invitation is then terminal

### Value objects

`UserId` · `Role` (Administrator, Member, Reader) · `EmailAddress`

### Relationships

```text
User ──1:N── Membership   (at most one active)
Invitation ──(accepted)──▶ Membership

Membership ──1:1── Role
```

### Domain events

`MemberInvited` — published in slice 8. This is the platform's first event, chosen
because only Identity events are available in Horizon 1; every event in `idea.md` §16
depends on delivery data that does not exist until slice 11.

Later: `MemberJoined`, `MemberRemoved`, `MemberRoleChanged`.

---

## Deferred contexts

Sketched only, to confirm the boundaries hold. Each is specified by its own slice.

### Integration (slice 9)

`Connection` (aggregate root — one per external system), `SyncRun`,
`RawPayload`. Credentials are **references** to Key Vault, never values (Principle V).

### Delivery (slices 11–12)

`WorkItem`, `WorkItemHistory`, `Sprint` as projections; `Risk`, `HealthScore` as native
aggregates. `HealthScore` carries its contributing factors so the score is explainable
without recomputation.

### AI Platform (slice 13)

`Capability` (e.g. `ReleaseRiskAnalysis` — ADR-009), `Prompt` (versioned),
`Invocation` (caller, capability, model, tokens, cost, latency, outcome), `Evaluation`.

---

## Open question for slice 9

**Is Capacity reachable at all?** It depends on estimates, availability, and team
allocation being recorded consistently in the source system — and in real Jira
installations they frequently are not.

Slice 9's proof deliberately requires writing down what surprised you about the real
data. Capacity is the concept most likely to be revealed as unbuildable, and finding
that out at slice 9 is much cheaper than assuming it and discovering it at slice 12.
