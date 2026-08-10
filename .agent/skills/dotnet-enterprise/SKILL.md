---
name: dotnet-enterprise
description: Use when writing or reviewing any .NET, C#, ASP.NET Core, or EF Core code in this repo.
---

# .NET Enterprise

Stack per [ADR-002](../../../docs/adr/ADR-002-dotnet-first.md): .NET LTS, C#,
ASP.NET Core, EF Core, xUnit.

## Project layout

One service = four projects. Created by the slice that needs the service, not upfront.

```
src/<Service>/
  <Service>.Api/             endpoints, DI wiring, middleware
  <Service>.Application/     use cases, DTOs, interfaces
  <Service>.Domain/          entities, aggregates, value objects, domain events
  <Service>.Infrastructure/  EF Core, external clients, implementations
```

`Domain` has **no** package references beyond the base library. If you find yourself
adding `Microsoft.EntityFrameworkCore` to Domain, the design is wrong — declare an
interface in Domain and implement it in Infrastructure.

## Non-negotiables

- **Nullable reference types enabled**, warnings as errors. Do not suppress with `!`
  without a comment justifying it.
- **`sealed` by default** on classes not designed for inheritance.
- **No `async void`.** Ever.
- **`CancellationToken` threaded through** every async call, from endpoint to database.
- **No `DateTime.Now`.** Inject a clock abstraction — otherwise time-dependent logic is
  untestable.
- **No secrets in `appsettings.json`.** User Secrets locally, Key Vault in Azure
  (Principle V).

## Domain modelling

Strongly-typed IDs, not raw `Guid`:

```csharp
public readonly record struct TenantId(Guid Value)
{
    public static TenantId New() => new(Guid.CreateVersion7());
}
```

This prevents passing a `UserId` where a `TenantId` is expected — a class of bug that is
invisible with raw `Guid` and consequential in tenant-scoped code.

**Invariants live on the aggregate.** A `Tenant` must never be able to lose its last
administrator. Enforce it in the aggregate, not in a service method that callers can
bypass:

```csharp
public void RemoveMember(UserId userId)
{
    var membership = _memberships.Single(m => m.UserId == userId);
    if (membership.Role == Role.Administrator && AdministratorCount == 1)
        throw new DomainException("A tenant must retain at least one administrator.");
    ...
}
```

Prefer `record` for value objects, `class` for aggregates with identity and lifecycle.

## EF Core

- **`IEntityTypeConfiguration<T>` per entity.** No attribute mapping, no `OnModelCreating`
  megamethod.
- **Global query filter for tenant scoping** — see the `security` skill. This is the
  load-bearing isolation mechanism; do not write per-query tenant predicates.
- **Migrations are reviewed like code.** Check the generated SQL before committing.
- **`AsNoTracking()` for reads.** Tracking is for mutations.
- **No lazy loading.** Be explicit about what you load.
- **Concurrency tokens** on entities that can be edited concurrently — `Membership`
  especially, since two administrators may edit the same member (spec 001 FR-021).

## API shape

REST, per `idea.md` §21.

- Tenant context comes from the **authenticated principal**, never from a route or query
  parameter a caller can set (Principle IV).
- `401` unauthenticated · `403` unauthorized · `404` for both "not found" and "exists but
  inaccessible" — these must be indistinguishable (spec 001 FR-009).
- Problem Details (RFC 7807) for errors. Never leak internal detail or stack traces
  (FR-022).
- Idempotency keys on creation endpoints (FR-020).

## Testing

xUnit. Details in the `testing` skill.

- Domain logic: pure unit tests, no mocks needed
- Application: unit tests with fakes over mocks where practical
- Infrastructure: integration tests against a **real** database in a container, not a
  fake provider — an in-memory provider will not catch a broken query filter

## Rationalizations that mean the layering is about to break

| Thought | Reality |
|---------|---------|
| "I just need one EF Core attribute on this entity, it's not a real dependency" | It is — Domain now references EF Core. The next person sees it works and adds a real one. Declare the interface in Domain, implement it in Infrastructure. |
| "A raw Guid is fine here, I'll remember which one it is" | You will, for a while. The next caller who passes a UserId where a TenantId belongs won't get a compiler error — that's the entire reason strongly-typed IDs exist. |
| "This validation is simple, I'll put it in the service instead of the aggregate" | A service method callers can bypass isn't an invariant, it's a suggestion. `Tenant` losing its last administrator is a broken model if any code path can reach it. |
| "async void is simpler here, it's just a fire-and-forget handler" | Exceptions from `async void` crash the process instead of surfacing to a caller. There's no scenario in this codebase where that's the acceptable trade. |
| "I'll add the CancellationToken parameter later if we need cancellation" | Threading it through later means touching every call site again. It costs nothing to add now and everything to retrofit. |
| "DateTime.Now is fine, I'm not writing a test for this yet" | You will eventually need to test time-dependent logic, and by then `DateTime.Now` is scattered through the code with no seam to inject a fake clock. |

## Red flags — stop and re-check

- Any package reference in a `Domain` project beyond the base library
- A raw `Guid` parameter where a strongly-typed ID belongs
- An invariant enforced in a service method instead of on the aggregate
- `async void` anywhere outside a framework-required signature
- A missing `CancellationToken` on an async call
- `DateTime.Now`/`DateTime.UtcNow` called directly instead of through an injected clock
- A domain entity returned directly from an endpoint instead of mapped to a DTO

**All of these mean: stop, and fix the layering before it compiles into a habit the next PR copies.**

## Common mistakes in this codebase's shape

- Putting EF attributes or `DbContext` references in Domain
- Forgetting `CancellationToken`, so requests cannot be cancelled
- Returning domain entities directly from endpoints — map to DTOs
- `Guid` parameters where a strongly-typed ID belongs
- Writing a tenant predicate by hand instead of relying on the global filter, which
  looks safe and quietly diverges from it
