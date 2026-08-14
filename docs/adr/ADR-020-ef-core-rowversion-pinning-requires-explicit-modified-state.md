# ADR-020: Pinning a RowVersion for optimistic concurrency requires explicit EntityState.Modified

**Status**: **Accepted**
**Date**: 2026-08-12
**Deciders**: Project owner (via T087/T097 review discipline)
**Relates to**: `specs/001-auth-tenant-management` FR-021 · Task 87, Task 58 (`.superpowers/sdd/tasks/progress.md`)

## Context

FR-021 requires optimistic concurrency: a `PATCH` with a stale `If-Match` (rowversion) must be
rejected with `409`/`412`, never silently applied over a concurrent change. The established
pattern in this codebase (`TenantEndpoints.cs`, `MemberEndpoints.cs`) is to load the entity,
pin the tracked entry's `RowVersion` shadow/concurrency property to the value the client
presented via `entry.Property(nameof(RowVersion)).OriginalValue = clientRowVersion`, mutate the
entity, and call `SaveChangesAsync()` — trusting EF Core to compare `OriginalValue` against the
database's current value and throw `DbUpdateConcurrencyException` on a mismatch.

That trust is only partially correct. EF Core's `ChangeTracker.DetectChanges()` decides whether
an entry needs a `SaveChanges` round-trip at all by looking at whether any **current value**
differs from any **original value** among the entity's *own* properties — not by looking at
whether `OriginalValue` was pinned. If the caller's mutation happens to be a no-op at the value
level (a rename to the same name, a role "change" to the same role — plausible, legitimate
requests, not just adversarial ones), `DetectChanges` sees the entry as `Unchanged` and skips
the `UPDATE` statement entirely. The pinned `RowVersion.OriginalValue` is compared against the
database **only inside the `UPDATE`'s `WHERE` clause**, which never executes. The request
returns success with no error, no concurrency exception, and no indication that the
concurrency check never ran — a stale or actively-racing `If-Match` silently "succeeds."

This was discovered twice in this project: first in T087's own new code for
`ChangeMemberRole`, and then — because the discovery prompted a search for the same pattern
elsewhere — found to **already exist**, unnoticed, in Phase 3's shipped, previously-reviewed
`TenantEndpoints.cs` (T058's `PATCH /tenants/{tenantId}`). That code had passed review earlier
in the project; nothing in `plan.md`, `research.md`, or any ADR anticipated this EF Core
behavior. It is a genuine implementation-time discovery, not a corner someone cut.

This is not project-specific. Any service using EF Core's built-in `RowVersion`/`Timestamp`
concurrency tokens with the "load, pin `OriginalValue`, mutate, save" pattern is exposed to it
whenever a legitimate request can be a same-value no-op.

## Decision

Whenever a tracked entity's `RowVersion.OriginalValue` is pinned to a client-supplied value for
an optimistic-concurrency check, the entry's state **must** also be forced to `Modified`
explicitly, immediately before `SaveChangesAsync()`:

```csharp
entry.Property(nameof(RowVersion)).OriginalValue = clientRowVersion;
// ... apply the caller's mutation ...
entry.State = EntityState.Modified; // forces the UPDATE + WHERE clause to run
                                      // even if no property's *value* actually changed
await dbContext.SaveChangesAsync();
```

This guarantees `SaveChanges` always issues the `UPDATE`, and therefore always evaluates the
`WHERE RowVersion = @clientRowVersion` clause, regardless of whether the caller's mutation was a
value-level no-op.

## Consequences

### Positive

- The concurrency check is now unconditional: it runs for every request that presents an
  `If-Match`, not only for requests whose mutation happens to change a value.
- The fix is small, local, and mechanical — one line per save path, no schema or API change.

### Negative

- **Every future save path that pins a `RowVersion.OriginalValue` must remember to also force
  `EntityState.Modified`.** This is not enforced by the type system or a compiler warning; it
  is a convention that must be re-applied correctly by hand at each new call site, exactly the
  kind of thing that was missed twice already in this project.
- Forcing `Modified` on a genuinely-unchanged entity means EF Core will issue an `UPDATE`
  statement (touching every mapped column, or the DB provider's equivalent) even when nothing
  besides the rowversion check actually needed to run. This is a minor, accepted cost — not a
  correctness problem — but it does mean a same-value `PATCH` is not free the way it would be
  if `DetectChanges` were left to decide.

### Neutral / accepted trade-offs

- This is specific to EF Core's default change-tracking-driven `SaveChanges` pipeline. It does
  not apply to `ExecuteUpdate`/`ExecuteDelete` (which bypass the change tracker and concurrency
  tokens entirely — a separate, already-documented hazard in `research.md` R3 item 6) or to
  raw SQL with an explicit `WHERE RowVersion = ...` clause (which does not rely on
  `DetectChanges` at all).

## Alternatives Considered

### Always mutate at least one real property, even to the same value, to force a "change"

Rejected: this relies on the caller's request always containing a mutation, which is not
guaranteed (a `PATCH` with an unchanged payload is a legitimate, spec-compliant request whose
concurrency token must still be checked), and it is *more* fragile than forcing `Modified`
directly, since it depends on EF Core's value-comparison semantics for the specific property
type rather than being an explicit, auditable statement of intent.

### Write a raw-SQL `UPDATE ... WHERE RowVersion = @x` for every concurrency-checked save

Rejected as inconsistent with the project's `research.md` R3 discipline of confining raw SQL to
a small, audited set of call sites (currently one: T075's row lock). Using raw SQL for every
optimistic-concurrency save would multiply that surface for no benefit over the one-line
`EntityState.Modified` fix.

### Add an automated regression test asserting `SaveChanges` always emits an `UPDATE` when `RowVersion.OriginalValue` is pinned, as a structural gate

Not adopted in this slice — the fix at both known call sites (`TenantEndpoints.cs`,
`MemberEndpoints.cs`) is covered by a dedicated regression test exercised against real EF Core
change tracking and a real database (see T087's unplanned-fix commit `1670c6a`), which is
sufficient for this slice's two call sites. A repo-wide architecture test (e.g. asserting every
method that reads `RowVersion.OriginalValue` also sets `EntityState.Modified` nearby) would be
a reasonable S3-style hardening but is not required by this ADR; noted under **Revisit When**.

## Revisit When

- A third save path introduces `RowVersion.OriginalValue` pinning. At that point, write the
  repo-wide architecture test described above rather than relying on a third manual catch.
- EF Core ships a first-class API for "always check this concurrency token regardless of
  `DetectChanges`" — if that ever exists, prefer it over the `EntityState.Modified` workaround.

## Compliance

- Enforced today only by code review and the two dedicated regression tests at the known call
  sites (`TenantEndpoints.cs`, `MemberEndpoints.cs`). There is no automated, repo-wide gate
  preventing a third occurrence of the original bug — that is a known weakness, not a neutral
  fact, tracked under **Revisit When** above.
