# Domain Model & Bounded Contexts

**Status**: Initial — covers what Horizons 1–2 need
**Date**: 2026-08-08
**Relates to**: `idea.md` §6, §14, §15, §19 · ADR-003 · Constitution Principle III
**Resolves**: [traceability U8](../traceability.md#u8--6s-14-delivery-entities-vs-46as-projections-not-native-entities)

## Bounded contexts

Four contexts, each owning its data exclusively (ADR-003). They are introduced by the
slice that needs them — not created up front.

| Context | Owns | Introduced |
|---------|------|-----------|
| **Tenancy** | Tenant, User, Membership, Invitation, Role | Slice 2 |
| **Integration** | Connection, Credential reference, Sync run, Raw payload | Slice 9 |
| **Delivery** | Canonical work data, Health score, Risk | Slices 11–12 |
| **AI Platform** | Capability, Prompt, Invocation, Cost record, Evaluation | Slice 13 |

**Engineering Intelligence is not a context in the MVP.** It is Horizon 3 Track D.

### Why Tenancy is separate from Delivery

Tenancy is a security boundary, and every other context depends on it. Keeping it
separate means the tenant-isolation rules (Principle IV) live in one place rather than
being re-implemented per context.

**Cross-context rule:** other contexts hold a `TenantId` **value**, not a reference to
the Tenancy database. They never join to it. Tenant validity is established once per
request, at the entry point.

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

## Tenancy context (slice 2)

The only context with a full specification today:
[specs/001-auth-tenant-management](../../specs/001-auth-tenant-management/spec.md).

### Aggregates

**Tenant** *(aggregate root)* — the isolation boundary and the root of all
tenant-scoped data.

- Identity: `TenantId`, system-generated, globally unique
- `DisplayName` — **not** globally unique; two unrelated companies may share a name
- `Status`, settings, creation metadata
- Invariant: **a Tenant always has at least one Administrator**

**User** *(aggregate root)* — a person, existing independently of any tenant.

- Identity: stable external identifier from Entra ID
- Email, display name
- May belong to several tenants (`idea.md` §19)
- Deliberately *not* inside the Tenant aggregate — a consultant is one person across
  several tenants, and modelling them per-tenant would duplicate identity

**Membership** *(aggregate root)* — binds one User to one Tenant with one Role.

- The unit that grants and revokes access, so it is the object authorization reads
- Exactly one Role
- Its own aggregate rather than part of Tenant, because it is contended: two
  administrators may edit membership concurrently, and locking the whole Tenant for
  that would be wrong

**Invitation** *(aggregate root)* — a pending offer of Membership to an email address.

- Intended Role, expiry (7 days), status: pending / accepted / revoked / expired
- Accepting it creates a Membership; the Invitation is then terminal

### Value objects

`TenantId` · `UserId` · `Role` (Administrator, Member, Reader) · `EmailAddress`

### Relationships

```text
Tenant ──1:N── Membership ──N:1── User
   │
   └──1:N── Invitation

Membership ──1:1── Role
```

### Domain events

`TenantCreated` — published in slice 8. This is the platform's first event, chosen
because it is the only one available in Horizon 1; every event in `idea.md` §16 depends
on delivery data that does not exist until slice 11.

Later: `MemberInvited`, `MemberJoined`, `MemberRemoved`, `MemberRoleChanged`.

---

## Deferred contexts

Sketched only, to confirm the boundaries hold. Each is specified by its own slice.

### Integration (slice 9)

`Connection` (aggregate root — one per tenant per external system), `SyncRun`,
`RawPayload`. Credentials are **references** to Key Vault, never values (Principle V).

### Delivery (slices 11–12)

`WorkItem`, `WorkItemHistory`, `Sprint` as projections; `Risk`, `HealthScore` as native
aggregates. `HealthScore` carries its contributing factors so the score is explainable
without recomputation.

### AI Platform (slice 13)

`Capability` (e.g. `ReleaseRiskAnalysis` — ADR-009), `Prompt` (versioned),
`Invocation` (tenant, capability, model, tokens, cost, latency, outcome), `Evaluation`.

---

## Open question for slice 9

**Is Capacity reachable at all?** It depends on estimates, availability, and team
allocation being recorded consistently in the source system — and in real Jira
installations they frequently are not.

Slice 9's proof deliberately requires writing down what surprised you about the real
data. Capacity is the concept most likely to be revealed as unbuildable, and finding
that out at slice 9 is much cheaper than assuming it and discovering it at slice 12.
