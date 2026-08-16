# Research: Architecture Tests (S3)

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Phase 0 output. One open question came into this phase from the spec's checklist — which
enforcement mechanism to use — and answering it empirically changed the answer to several
others. Every claim below was verified against this repository or by running code, not
reasoned about abstractly; where something remains unverified it says so.

---

## R1: Enforcement mechanism — parse declarations and source, not IL

**Decision**: Build the gates from three plain mechanisms already available with zero new
dependencies:

| Rule class | Mechanism | Why |
|---|---|---|
| Project-reference rules (FR-004, FR-005, FR-008) | Parse `.csproj` XML | Deterministic; catches a declared-but-unused reference too |
| Forbidden-package rules (FR-014, FR-016, FR-017, FR-018) | One pin over the whole package set in `Directory.Packages.props` | Clarified 2026-08-15: a deny-list cannot enumerate "or equivalent", so an unlisted package would pass a green gate |
| Raw-SQL allow-list (FR-010, FR-011) and model naming (FR-015) | Scan `.cs` source text under `src/` | FR-011 requires identifying entries by **file and member** — IL carries neither. FR-015 is scoped to `src/**/*.cs` so the scan does not fail on this repo's own docs |
| Absence pins and type queries (FR-009, FR-012, FR-013) | Plain reflection over built assemblies | Simple type-shape questions, no method-body analysis |
| Requirement coverage (FR-020-FR-022) | Reflection over the test assemblies' attributes | See R3 |

> Rule-class assignments for FR-014-FR-018 were refined by `/speckit.clarify` after this
> section was first written; the mechanism decision itself (no IL, no library) is unchanged.
> The full set of clarification-driven amendments is tabulated at the end of this document.

**No architecture-testing library is added.**

**Rationale**: NetArchTest was the obvious candidate — the project's own `testing` skill
writes its slice-3 example in NetArchTest syntax
(`Types.InAssembly(...).ShouldNot().HaveDependencyOnAny(...)`), so it was treated as the
front-runner and tested first rather than dismissed.

It restores and runs cleanly on .NET 10 (`NetArchTest.Rules` 1.3.2). But run against this
codebase's actual assemblies it **missed half of a known violation set**:

```
=== Tenancy.Application ===
  NetArchTest IsSuccessful (true = no infra dep): False
  IL-declared EF Core assembly refs: Microsoft.EntityFrameworkCore
  offending type: Tenancy.Application.Users.EnsureUserProvisioned

=== Tenancy.Domain ===
  NetArchTest IsSuccessful (true = no infra dep): True
  IL-declared EF Core assembly refs: (none)
```

Asked to enumerate *every* type depending on `Microsoft.EntityFrameworkCore`, it returned
exactly one of 32 types: `EnsureUserProvisioned`. It did not report
`Tenancy.Application.Invitations.InviteMember`, which carries a structurally **identical**
violation — verified directly:

| Site | Construct | Enclosing method | Reported by NetArchTest |
|---|---|---|---|
| `EnsureUserProvisioned.cs:73` | `catch (DbUpdateException)` | `async Task<User> ExecuteAsync` | ✅ yes |
| `InviteMember.cs:129` | `catch (DbUpdateException)` | `async Task<InviteMemberResult> ExecuteAsync` | ❌ **no** |

The likely cause is that a typed `catch` inside an `async` method compiles into a
compiler-generated state-machine type rather than the declaring class, and such types are
filtered from results — **but this is a hypothesis, not something verified**, and the
mechanism choice does not depend on which explanation is correct. What matters is the
observed behaviour.

A gate that catches one of two identical violations is worse than no gate: it reports green
while the boundary is broken, which is precisely the false confidence Principle VII exists
to remove. By contrast, reading the `<PackageReference>` declaration finds this violation
with certainty, because the declaration is what the rule is actually about — "this project
may not depend on EF Core" is a statement about the dependency graph, not about which types
happen to touch it.

**Alternatives considered**:

- **NetArchTest.Rules 1.3.2** — rejected on the evidence above. Worth revisiting only if a
  future rule genuinely needs type-level analysis that declarations cannot express, and only
  after confirming the async-state-machine behaviour is resolved. It is not needed for any
  rule in this slice.
- **ArchUnitNET (`TngTech.ArchUnitNET` 0.13.3)** — available and more capable, but it is the
  same class of tool operating on the same IL, so it plausibly shares the same blind spot.
  Not tested, because R1's rules do not need IL analysis at all; adopting a second candidate
  to solve a problem we no longer have would be the "machinery without a consumer" error
  [ADR-021](../../docs/adr/ADR-021-application-layer-patterns-at-first-consumer.md) rejects.
- **A Roslyn analyzer** — the only mechanism that reliably inspects method bodies, and the
  only one that could enforce FR-019 structurally. Rejected as disproportionate: it is a
  separate build-integrated project, and R2 removes the requirement that motivated it.
- **Extending S2's existing `XDocument`-based approach** — this is effectively the chosen
  option. It is already proven in `CapabilityBoundaryTests`, needs no dependency, and the
  spec's FR-002 already requires migrating those tests, so the code is being touched anyway.

**Consequence for the spec**: none. FR-004/FR-005's requirement ("whether by project
reference or by package reference") is satisfiable exactly as written, and this mechanism is
strictly stronger than the IL alternative for that wording.

---

## R2: FR-019 — eliminate the failure mode instead of gating it

**Decision**: Amend the approach behind FR-019. Rather than building a gate that detects an
endpoint capable of surfacing `DomainException` as a `500`, make that outcome **impossible**:
add central `DomainException` → `400` and `ConflictException` → `409` mapping to
`ProblemDetailsHandler`, then prove it with tests.

**Rationale**: `ProblemDetailsHandler` currently sets
`StatusCodes.Status500InternalServerError` unconditionally, so correct behaviour depends on
every endpoint remembering its own `try/catch`. Today they do — verified across
`TenantEndpoints`, `InvitationEndpoints`, and `MemberEndpoints`, the last of which uses
result objects (`RemoveMemberResult`, `ChangeMemberRoleResult`) instead of exceptions. The
risk is the *next* endpoint.

Detecting "this handler could let a `DomainException` escape" is a method-body dataflow
question. No mechanism in R1 can answer it, and the one that could (a Roslyn analyzer) costs
more than the problem. But the requirement's actual intent — a client never receives `500`
for bad input — is fully served by making the default correct.

This is the stronger form of Principle VII. A gate detects the mistake; central mapping means
there is no mistake to detect. Existing endpoint `catch` blocks keep working unchanged, since
they run before the handler is ever reached, so the change is additive with no regression risk
to their more specific messages.

**Alternatives considered**:

- **Roslyn analyzer over endpoint handlers** — the only structural answer. Rejected as
  disproportionate for one convention, and it would still leave `ProblemDetailsHandler`'s
  blanket `500` as the underlying defect.
- **Integration test hitting every endpoint with invalid input** — genuinely useful and
  partly retained (see below), but on its own it enforces nothing about endpoints added
  later, and it requires knowing a `DomainException`-triggering input for each route.
- **Leave the convention to human review** — what ADR-021 records as the status quo and
  explicitly labels a known weakness. Rejected; that ADR names this slice as where it closes.

**Consequence for the spec**: FR-019 is amended in scope — from "a gate that fails when an
endpoint can surface a `DomainException` as `500`" to "central mapping such that an
unhandled `DomainException` yields `400` and `ConflictException` yields `409`, proven by
test". The client-visible guarantee is unchanged and better enforced. This is recorded as an
amendment rather than done silently, because the spec is the authority the plan answers to.

---

## R3: Requirement-coverage declarations — a custom attribute, not xUnit traits

**Decision**: Declare coverage with a purpose-built attribute applied to test methods or
classes, e.g. `[CoversRequirement("FR-007")]`, discovered by reflection over the test
assemblies.

**Rationale**: FR-022 requires the gate to fail when a declaration names a requirement
identifier absent from spec 001. That is a validation rule about the declaration itself, which
means the identifiers must be enumerable and checkable — a dedicated attribute type gives one
obvious place to put both the declaration and its validation, and makes a typo a test failure
rather than silent non-coverage.

`[Trait("FR", "FR-007")]` was the alternative: idiomatic xUnit, no new type, and filterable
from the CLI via `dotnet test --filter`. Rejected because its value is a bare string with no
schema, it reads identically whether the key is `FR`, `Fr`, or `fr`, and nothing prevents two
tests using different key spellings — so the gate would end up validating trait keys as well
as values. The CLI-filtering benefit is real but incidental to this requirement.

Spec 001's requirement identifiers are FR-001 through FR-026 — **verified**: 26 definitions,
contiguous, with `old-FR-0NN` entries in its Deferred Requirements table being separate
historical identifiers that must not be accepted by the gate.

**Alternatives considered**:

- **Parse `coverage.md`'s prose** — already rejected in the spec itself (Revision Note 5),
  because that file cites tests inconsistently and a gate producing false failures gets
  disabled.
- **xUnit `[Trait]`** — as above.
- **A hand-maintained mapping file in the test project** — a second artifact to drift from the
  tests, which is the problem `coverage.md` already demonstrates.

---

## R4: Raw-SQL detection must be source-based, and there is exactly one call site

**Decision**: Detect raw-SQL constructs by scanning `.cs` source files under `src/`, with the
allow-list keyed by relative file path plus enclosing member name.

**Rationale**: FR-011 requires each allow-list entry to bind file **and** member so that
moving or renaming an audited call site fails the gate. Compiled IL carries neither a source
path nor a reliable member boundary for an inlined or state-machine-hoisted call, so a
source-text scan is the only mechanism that can satisfy the requirement as written. It also
detects a raw-SQL call in code that is never executed, which an IL/runtime approach might not.

The current state is **verified**: exactly one raw-SQL construct exists in the whole
repository —
`src/Tenancy/Tenancy.Infrastructure/Persistence/MembershipRepository.cs:100`, inside
`RemoveMembershipAsync`, the `UPDLOCK, HOLDLOCK` tenant row lock that
[research.md R3 of spec 001](../001-auth-tenant-management/research.md) names as the sole
audited exception. Constructs searched for: `FromSqlRaw`, `FromSqlInterpolated`,
`ExecuteSqlRaw`, `ExecuteSqlInterpolated`, their async forms, and `Database.SqlQuery`.

**Alternatives considered**:

- **IL/reflection detection of `RelationalDatabaseFacadeExtensions` calls** — cannot produce
  file or member, so it cannot satisfy FR-011, and R1 showed IL analysis of async method
  bodies is unreliable here anyway.
- **A Roslyn analyzer** — would be accurate and could report file and line precisely. Held in
  reserve: if the source scan proves brittle against formatting (a call split across lines),
  this is the escalation path. Noted as a risk in the plan rather than adopted pre-emptively.

---

## R5: Background-job and absence pins

**Decision**: Enforce FR-012 by reflection: find types implementing `IHostedService` or
deriving from `BackgroundService` in the built assemblies, and assert none of them declares a
constructor dependency on `TenancyDbContext` or on any **persistence port**.

> **Refined by clarification (2026-08-15).** This section originally said "a tenant-scoped
> repository interface", which left the set undefined — `IUserRepository` documents itself as
> *not* a tenant-scoped read, and `IMembershipDirectory` is the sanctioned cross-tenant one, so
> "tenant-scoped" did not partition the ports cleanly. The set is now every persistence port,
> identified mechanically as a port whose implementation lives in a persistence namespace, so
> S9's and S11's future ports are covered without curating a list. `ITenantContext` is excluded:
> it carries no persistence implementation and is what a job would legitimately use.
> The same session also settled that this slice builds **no** sanctioned replacement
> abstraction — its shape belongs to the first real consumer at S8/S10 — so the gate must name
> what to do instead rather than merely blocking.

**Rationale**: Constructor-parameter inspection is a type-shape question that plain reflection
answers reliably — unlike the method-body questions R1 showed to be unreliable. It is also the
correct place to look, because these are DI-injected dependencies: a background job gets its
data access through its constructor, so a job that cannot be *constructed* with a
`TenancyDbContext` cannot use one.

This is deliberately weaker than "the job establishes tenant context before querying", which
is a dataflow property. The spec already chose the structural form for exactly this reason
(User Story 4 rejects the "sets context in the same type" heuristic as false-positive-prone).

**Verified**: zero occurrences of `IHostedService`, `BackgroundService`, or
`AddHostedService` across `src/` and `tests/`, so FR-013's pin records a checked fact. The
same holds for FR-016 — the full central package list is thirteen entries, all EF Core,
ASP.NET Core, `Microsoft.Identity.Web`, or test infrastructure, with no model provider SDK.

**Open item, deferred to implementation**: FR-012's gate has no positive case to test against
while no background job exists, so proving it can fail (FR-023) requires temporarily
introducing one. The plan schedules that as an explicit, reverted step rather than leaving
the gate unproven.

---

## Summary of spec amendments arising from research

| Requirement | Change | Driver |
|---|---|---|
| FR-019 | Scope amended: central exception→status mapping proven by test, instead of a structural gate over endpoint handlers | R2 — the structural form needs a Roslyn analyzer, and central mapping removes the failure mode outright |
| FR-012 | "Tenant-scoped repository" replaced by a mechanical "persistence port" definition; no replacement abstraction built in this slice | `/speckit.clarify` — the original set did not partition the ports cleanly and named an abstraction that does not exist |
| FR-014, FR-017, FR-018 | Implemented as one pin over the whole package set instead of three per-package deny-lists | `/speckit.clarify` — "or equivalent" cannot be enumerated, so a deny-list is bypassed by an unlisted package |
| FR-015 | Scope and pattern set fixed: `src/**/*.cs` only, six explicit prefixes; docs, specs, and tests out of scope | `/speckit.clarify` — a repo-wide scan would fail on this repository's own documentation |

No other requirement changed. FR-004/FR-005's "project reference or package reference" wording
is satisfied exactly as written by R1's chosen mechanism.

## Residual risks

- **Source-text scanning is formatting-sensitive** (R4). A raw-SQL call split across lines, or
  written through an alias, could evade the scan. Mitigated by proving the gate red against a
  deliberately introduced call (FR-023) and by keeping a Roslyn analyzer as the documented
  escalation path — not by assuming the scan is complete.
- **NetArchTest's observed blind spot is characterised but not root-caused** (R1). This matters
  only if the library is reconsidered later; the recorded evidence is the observation, not the
  explanation.
- **FR-012's gate is proven only against a temporary fixture** (R5), because the code class it
  guards does not exist. That is inherent to writing the guardrail before the first job, which
  the spec chose deliberately.
