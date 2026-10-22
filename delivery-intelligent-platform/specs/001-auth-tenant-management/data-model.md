# Phase 1 Data Model: Tenancy (S2)

**Date**: 2026-08-09 · **Spec**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Implements the Tenancy context of
[docs/architecture/domain-model.md](../../docs/architecture/domain-model.md). Aggregate
boundaries there are authoritative; this document adds persistence shape, invariants, and
the isolation configuration.

---

## Isolation classification — read this first

Every entity falls into exactly one of three buckets. The bucket determines whether the
global tenant filter applies, and getting it wrong is the leak.

| Bucket | Entities | Filter |
|---|---|---|
| **Tenant-owned** — implements `ITenantOwned` | `Membership`, `Invitation`, `IdempotencyRecord` | Named `TenantFilter` applied automatically |
| **The tenant itself** | `Tenant` | Filtered on its own `Id == current tenant` |
| **Not tenant-scoped** | `User` | No filter — a person exists independently of any tenant and may belong to several |

`User` carrying no tenant filter is deliberate and is the entity most likely to be
misclassified by a future contributor. A `User` row is not a tenant's data; the *membership*
is. Adding a tenant filter to `User` would break FR-010 (one person, several tenants); adding
a `TenantId` column to it would be modelling the same person once per tenant, which
`domain-model.md` explicitly rejects.

---

## Tenant *(aggregate root)*

The isolation boundary and the root of all tenant-scoped data.

| Field | Type | Notes |
|---|---|---|
| `Id` | `TenantId` (`Guid` v7) | PK. System-generated. `Guid.CreateVersion7()` — sequential, so it does not fragment the clustered index the way v4 does. |
| `DisplayName` | `string(200)` | **Not globally unique** (spec edge case). Required, trimmed, non-empty. |
| `Status` | `TenantStatus` | `Active` \| `Suspended`. Stored as `string`, not `int` — an enum stored as an ordinal is unreadable in the database and breaks on reorder. |
| `Settings` | owned type | Table-split onto `Tenants`. Empty in this slice; the seam exists because FR-006 names settings. |
| `CreatedAtUtc` | `DateTimeOffset` | From the injected clock, never `DateTime.Now`. |
| `CreatedByUserId` | `UserId` | Value, not an FK-enforced navigation to a cross-context entity. |
| `RowVersion` | `byte[]` | `.IsRowVersion()` — FR-021. |

**Invariant: a tenant always retains at least one active Administrator (FR-015).**

This is the invariant that decides the aggregate boundary, and it is worth being precise
about because it is easy to get wrong in both directions.

`Membership` is its own aggregate root (`domain-model.md`: memberships are contended, and
locking the whole tenant to change one member's role would be wrong). But the
last-administrator rule spans *all* memberships of a tenant — so it cannot be enforced inside
a single `Membership`.

Enforcement, therefore, is layered — and honestly labelled:

1. **Domain** — a `TenantAdministration` aggregate operation receives the tenant's current
   administrator count and refuses the removal or demotion. This is where the rule lives and
   where it is unit-tested.
2. **Database** — a `UNIQUE` filtered index cannot express "at least one", so this is *not*
   enforceable by constraint. Concurrency is instead handled by the `rowversion` on the
   memberships being changed plus the transaction: two administrators concurrently removing
   each other produce one success and one `409`.

**This is a genuine gap worth stating plainly**: two concurrent transactions each removing a
*different* administrator, when exactly two exist, could both observe a count of 2 and both
succeed under `READ COMMITTED` — leaving zero. Mitigation for this slice: perform the
administrator count and the membership write in one transaction at `SERIALIZABLE`, or take an
application lock on the tenant row (`UPDATE Tenants SET ... WHERE Id = @id` to acquire the
row lock) before counting. **Must be covered by a concurrent-removal integration test** — a
unit test cannot demonstrate it.

---

## User *(aggregate root)*

A person. Exists independently of any tenant (`domain-model.md`).

| Field | Type | Notes |
|---|---|---|
| `Id` | `UserId` (`Guid` v7) | PK. **Internal** identifier we own. |
| `EntraObjectId` | `string(64)` | The `oid` claim. |
| `EntraTenantId` | `string(64)` | The `tid` claim. |
| `Email` | `EmailAddress` | Normalised lowercase. From `preferred_username`/`email` — **display and invitation matching only, never authorization** (research R2). |
| `DisplayName` | `string(200)` | |
| `CreatedAtUtc` | `DateTimeOffset` | |
| `LastSeenAtUtc` | `DateTimeOffset` | Set on authentication. Supports FR-025's logging without a separate store. |
| `RowVersion` | `byte[]` | |

**`UNIQUE (EntraTenantId, EntraObjectId)`** — the composite is the identity (research R2).
`oid` alone is *not* globally unique across Entra tenants; a unique index on `EntraObjectId`
alone would be a latent bug that only appears with a B2B guest or a second Entra tenant.

Users are provisioned **just-in-time** on first authenticated request, keyed on that
composite. No user administration endpoint exists in this slice.

---

## Membership *(aggregate root, tenant-owned)*

Binds one `User` to one `Tenant` with exactly one `Role`. **The object authorization reads**
(ADR-017 step 2), so its read path is the hottest in the system.

| Field | Type | Notes |
|---|---|---|
| `Id` | `MembershipId` (`Guid` v7) | PK |
| `TenantId` | `TenantId` | Filtered. Stamped by the interceptor, **immutable** thereafter. |
| `UserId` | `UserId` | |
| `Role` | `Role` | `Administrator` \| `Member` \| `Reader`. Stored as `string`. |
| `Status` | `MembershipStatus` | `Active` \| `Removed`. Soft-removed so FR-025 can report *who* lost access and when. |
| `CreatedAtUtc`, `RemovedAtUtc` | `DateTimeOffset?` | |
| `RowVersion` | `byte[]` | FR-021 — two administrators editing the same member (spec edge case). |

Indexes:

- **`UNIQUE (TenantId, UserId) WHERE Status = 'Active'`** — a filtered unique index. Makes
  duplicate active membership impossible at the database level rather than by application
  check, which is what makes the spec's "invitation to an existing member" edge case a `409`
  by construction.
- **`(TenantId, UserId, Status) INCLUDE (Role)`** — covering index for the ADR-017 resolution
  lookup. ADR-017 records this as not optional: it is on the hot path of every tenant-scoped
  request.
- `(UserId)` — for `GET /tenants`, the audited cross-tenant helper.

---

## Invitation *(aggregate root, tenant-owned)*

| Field | Type | Notes |
|---|---|---|
| `Id` | `InvitationId` (`Guid` v7) | PK |
| `TenantId` | `TenantId` | Filtered |
| `Email` | `EmailAddress` | Normalised lowercase. **Untrusted until the invited identity authenticates as that address** (FR-013). |
| `Role` | `Role` | Intended role |
| `Status` | `InvitationStatus` | `Pending` \| `Accepted` \| `Revoked` \| `Expired` |
| `TokenHash` | `byte[32]` | **SHA-256 of the token. The token itself is never stored** — it is a credential, and a stored credential is a leaked credential (Principle V). Returned once, at creation. |
| `ExpiresAtUtc` | `DateTimeOffset` | Creation + 7 days (Assumption 6) |
| `CreatedAtUtc`, `CreatedByUserId` | | |
| `AcceptedAtUtc`, `AcceptedByUserId` | nullable | |
| `RowVersion` | `byte[]` | Prevents double-accept under a race |

- **`UNIQUE (TenantId, Email) WHERE Status = 'Pending'`** — one pending invitation per address
  per tenant, enforced by the database. This is also what makes FR-020's idempotency correct
  even if the idempotency layer is bypassed.
- `UNIQUE (TokenHash)`

**`Expired` is derived, not swept.** Acceptance checks `ExpiresAtUtc` against the clock; the
status column is a materialisation for listing. A background job would need explicit tenant
context (the `distributed-systems` skill's most dangerous case) and there is no such job in
this slice — deliberately.

---

## IdempotencyRecord *(tenant-owned, infrastructure)*

Supports FR-020. Design rationale in research R6.

| Field | Type | Notes |
|---|---|---|
| `TenantId` | `TenantId?` | Nullable — `POST /tenants` has no tenant yet. Then keyed by `CreatedByUserId`. |
| `Key` | `string(255)` | Client-supplied `Idempotency-Key`, opaque |
| `Endpoint` | `string(200)` | |
| `RequestHash` | `byte[32]` | SHA-256 of the canonicalised body |
| `Status` | `tinyint` | `0 = InFlight`, `1 = Completed` |
| `StatusCode`, `ResponseBody`, `ResourceLocation` | nullable | Replayed verbatim |
| `CreatedAtUtc`, `ExpiresAtUtc` | `DateTimeOffset` | TTL 24h |

**PK `(TenantId, Endpoint, Key)`** — the unique key *is* the concurrency control. Scoping by
tenant is a security requirement, not tidiness: a global key namespace would let one tenant
probe another's key usage.

---

## Value objects

`TenantId` · `UserId` · `MembershipId` · `InvitationId` · `Role` · `EmailAddress`

Strongly-typed IDs as `readonly record struct`, per the `dotnet-enterprise` skill:

```csharp
public readonly record struct TenantId(Guid Value)
{
    public static TenantId New() => new(Guid.CreateVersion7());
}
```

This is not ceremony. In tenant-scoped code a `UserId` passed where a `TenantId` belongs is a
cross-tenant bug that raw `Guid` gives the compiler no way to catch.

`Guid.CreateVersion7()` over v4 because v7 is time-ordered — random GUIDs as clustered keys
cause page splits and index fragmentation on every insert.

---

## Entity relationships

```text
User ──N:1── Membership ──N:1── Tenant
                                  │
                                  └──1:N── Invitation

Membership ──1:1── Role   (value object)
```

`Membership` is the only path from `User` to `Tenant`. There is no direct navigation, so
there is no way to load a user's tenants without going through the audited helper.

---

## EF Core configuration

One `IEntityTypeConfiguration<T>` per entity — no attribute mapping, no `OnModelCreating`
megamethod (`dotnet-enterprise` skill).

```csharp
// Applied by iterating the model, so a new tenant-owned entity cannot be forgotten.
foreach (var et in modelBuilder.Model.GetEntityTypes()
         .Where(e => e.BaseType is null && typeof(ITenantOwned).IsAssignableFrom(e.ClrType)))
{
    var p = Expression.Parameter(et.ClrType, "e");
    var body = Expression.Equal(
        Expression.Property(p, nameof(ITenantOwned.TenantId)),
        Expression.Property(Expression.Constant(this), nameof(TenantId))); // instance member → SQL parameter
    modelBuilder.Entity(et.ClrType)
        .HasQueryFilter("TenantFilter", Expression.Lambda(body, p));
}
```

Four points, each load-bearing:

1. **Iterate the model, don't hand-write per entity.** A developer must not be able to omit
   the filter by forgetting to add it (ADR-013 mechanism 1).
2. **Name the filter `TenantFilter`** (EF Core 10). Named filters let the one audited
   cross-tenant helper bypass *only* this filter. **A bare `IgnoreQueryFilters()` is
   prohibited** — it disables all of them.
3. **`Expression.Property(Expression.Constant(this), ...)`** — a member access on the context
   instance, so EF lifts it to a SQL parameter and one cached plan serves every tenant. A
   captured local becomes an inlined constant: a compiled model per tenant, plus a real
   staleness risk.
4. **Compiled models must stay off** — they do not support global query filters at all
   (efcore#24897). A future performance pass enabling them would silently remove isolation.

Plus a scoped `SaveChangesInterceptor` that stamps `TenantId` on insert and rejects any
modify/delete whose original `TenantId` differs. Query filters are read-side only, so nothing
else stops an attached stub entity carrying a foreign tenant's key from being written.

---

## Migrations

- Single initial migration `InitialTenancy`.
- **Read the generated SQL before committing** (`dotnet ef migrations script`) — a rename can
  come out as a drop.
- `dotnet ef migrations has-pending-model-changes` in the build.
- `MigrateAsync()` at startup, Development only. Production path (bundle + separate
  DDL identity) is S6/S7 — research R8.
- `EnsureCreated()` is prohibited: it bypasses migrations and then makes `Migrate()` fail.
