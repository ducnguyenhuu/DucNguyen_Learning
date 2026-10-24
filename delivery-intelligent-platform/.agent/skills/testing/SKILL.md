---
name: testing
description: Use when writing tests, deciding what to test and at which level, or judging whether a slice or feature is actually done.
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

Also enforced since slice 3
([U12](../../../docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs)):

- Raw SQL execution restricted to audited helpers (`RawSqlGates`)
- Background jobs must not hold a `DbContext` or persistence port captive
  (`BackgroundJobGates`)

**Verify an architecture test can fail.** Introduce the violation, watch the build break,
revert. An architecture test that never could have failed is decoration.

## What to test at each level

| Level | Test | Do not test |
|-------|------|-------------|
| Unit | Domain invariants, business rules, calculations | Framework behaviour, mapping |
| Integration | Queries, migrations, **authorization**, transactions, locks | Third-party internals |
| Contract | Published API and event shapes | Implementation |
| Architecture | Boundaries, dependency direction | Behaviour |
| E2E | One critical path per slice | Everything |

**Integration tests use a real database in a container.** An in-memory provider will not
enforce filtered unique indexes, application locks, or the audit trigger — which is
precisely where the concurrency and audit bugs live.

## Authorization tests are not ordinary tests

Every member-only route needs a test proving an authenticated non-member gets 403
(`MembershipResolutionTests`), and every administrator-only route needs one proving Member
and Reader get 403 (`RolePermissionMatrixTests`). No exceptions.

Pattern: seed a caller with the wrong standing, call the route, assert refusal *and* that
nothing changed in the database.

Write it to fail first (`idea.md` §59.2). A green authorization test that was never red
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
- Container Apps: a revision broken and recovered
- Authorization: a test that actually caught a non-member and a non-administrator

Demonstrating the happy path proves nothing worth knowing.

## Requirement coverage

Every functional requirement in the slice's spec maps to at least one test (spec 001
SC-006). If an FR has no test, either write it or challenge the FR — an untestable
requirement is a badly written one.

## Rationalizations that mean a test is not actually testing anything

| Thought | Reality |
|---------|---------|
| "I wrote the test after, but I ran it and it passes" | A test written after the code, passing on the first run, has never been proven capable of failing. That's the one thing a test must do. |
| "It's a simple authorization test, I don't need to watch it fail first" | Authorization tests are exactly where this matters most, and a green one that was never red has caught nothing. |
| "The in-memory provider is faster and tests the same logic" | It doesn't enforce filtered unique indexes, locks or triggers the way a real database does — which is precisely the bug class that matters most here. |
| "I'll add the architecture test later, the rule is documented anyway" | Documentation is not enforcement. Principle VII exists because human review doesn't scale and doesn't remember; an undocumented-but-enforced rule beats a documented-but-unenforced one. |
| "This covers three behaviors, splitting it into three tests is overkill" | One assertion-heavy test that fails tells you nothing about which of the three broke. Split it before it fails, not after. |
| "It worked when I tried it manually, that's good enough for this slice" | "Compiles" and "worked once" are not the definition of done — the slice's Proof checklist in roadmap.md is. |

## Red flags — stop and re-check

- A test that passed the first time it was ever run
- A member-only or administrator-only route with no authorization test in the same PR
- An integration test running against an in-memory provider instead of a real database
- An architecture test nobody has verified can actually fail
- A functional requirement in the spec with no test mapped to it
- Claiming a slice is done without checking its Proof checklist

**All of these mean: stop, write or re-run the test red-first, and don't mark anything done until it demonstrably could have failed.**

## Anti-patterns

- Testing mocks instead of behaviour
- Mocking the database in an integration test — that is a unit test in costume
- One test asserting fifteen things, so a failure tells you nothing
- Tests coupled to implementation, so refactoring breaks them
- Snapshot tests standing in for meaningful assertions
- `Thread.Sleep` instead of proper async waiting
