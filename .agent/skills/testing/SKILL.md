---
name: testing
description: Test strategy, architecture tests, and the definition of done for this platform. Load when writing tests, deciding what to test, or judging whether a slice is complete.
---

# Testing

Governed by [Constitution Principle VII](../../../.specify/memory/constitution.md):
anything that must always be true is enforced by a gate that fails the build. Human
review does not scale and does not remember.

## Test projects

```
tests/
  UnitTests/          domain + application logic, no I/O
  IntegrationTests/   real database in a container
  ContractTests/      service-to-service contracts (first real one at slice 9)
  ArchitectureTests/  boundaries, enforced
  EndToEndTests/      deployed environment (slice 7+)
```

`idea.md` §22 also lists Performance and Security tests. Both are legitimately
post-Gate-1 and currently unscheduled — see
[traceability U6](../../../docs/traceability.md#u6--22-lists-eight-test-types-only-four-are-scheduled).

## Architecture tests are the most valuable tests here

They convert architectural intent from documentation into an executable constraint. This
is what makes `idea.md` §52's "automated architecture governance" a result rather than an
aspiration.

Minimum set (slice 3):

```csharp
// Domain depends on nothing outward
Types.InAssembly(DomainAssembly)
     .ShouldNot().HaveDependencyOnAny(
         "Microsoft.EntityFrameworkCore", "Azure.", "Microsoft.AspNetCore")
     .GetResult().IsSuccessful.Should().BeTrue();

// No service touches another service's data layer
// No business assembly references a model provider SDK  (ADR-008 — load-bearing gate)
// No model name string outside AI Platform configuration (ADR-009)
```

Also required in slice 3, and currently missing
([U12](../../../docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs)):

- Raw SQL execution restricted to audited helpers — closes the likeliest cross-tenant
  leak path under ADR-013
- Background jobs must establish tenant context explicitly

**Verify an architecture test can fail.** Introduce the violation, watch the build break,
revert. An architecture test that never could have failed is decoration.

## What to test at each level

| Level | Test | Do not test |
|-------|------|-------------|
| Unit | Domain invariants, business rules, calculations | Framework behaviour, mapping |
| Integration | Queries, migrations, **tenant isolation**, transactions | Third-party internals |
| Contract | Published API and event shapes | Implementation |
| Architecture | Boundaries, dependency direction | Behaviour |
| E2E | One critical path per slice | Everything |

**Integration tests use a real database in a container.** An in-memory provider will not
catch a broken global query filter — which is precisely the bug that matters most.

## Tenant isolation tests are not ordinary tests

Every tenant-scoped operation needs one. Spec 001 SC-004 permits **zero** exceptions, and
Gate 1 blocks Horizon 2 until this holds across the board.

Pattern: seed two tenants, authenticate as tenant A, attempt every operation against
tenant B's data, assert refusal *and* that the response does not disclose existence.

Write it to fail first (`idea.md` §59.2). A green isolation test that was never red
proves nothing.

## TDD

For anything with logic, and for every bug fix:

1. Write the failing test. **Run it. Watch it fail.** A test that passes immediately is
   testing the wrong thing, or nothing.
2. Minimum code to pass.
3. Refactor.

For a bug: reproduce it as a failing test *first*. That test is both the proof the fix
works and the guard against regression.

## Definition of done

Not "the code compiles" and not "it worked when I tried it." A slice is done when its
**Proof** checklist in [roadmap.md](../../../roadmap.md) is fully checked.

This project is research-first (`idea.md` §59.2): **a technology is not proven until it
has been driven under failure conditions.**

- Service Bus: a duplicate handled idempotently, a dead letter replayed
- Sync engine: a rate limit survived, a mid-sync kill resumed
- AKS: a rollout broken and recovered
- Multi-tenancy: a test that actually caught a cross-tenant read

Demonstrating the happy path proves nothing worth knowing.

## Requirement coverage

Every functional requirement in the slice's spec maps to at least one test (spec 001
SC-006). If an FR has no test, either write it or challenge the FR — an untestable
requirement is a badly written one.

## Anti-patterns

- Testing mocks instead of behaviour
- Mocking the database in an integration test — that is a unit test in costume
- One test asserting fifteen things, so a failure tells you nothing
- Tests coupled to implementation, so refactoring breaks them
- Snapshot tests standing in for meaningful assertions
- `Thread.Sleep` instead of proper async waiting
