# Feature Specification: Architecture Tests

**Feature Branch**: `002-architecture-tests`
**Created**: 2026-08-15
**Revised**: 2026-08-15 (pre-plan review — see [Revision Notes](#revision-notes))
**Status**: Draft
**Input**: User description: "S3 — Architecture tests. Per roadmap.md: enforce domain≠infrastructure layering, no cross-service data access, no provider SDK outside AI Platform boundary, raw SQL restricted to audited helpers, background jobs must set tenant context (U12, docs/traceability.md). Done when: a deliberate domain→infrastructure reference fails the build; a deliberate cross-service data access fails the build; every FR in spec 001 maps to a test; full suite runs unattended under 5 minutes. Builds on existing tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs from S2's T089."

This slice has no end user. Its "user" is the **developer working in this repository**
(including a future AI agent) — the person whose accidental boundary violation must be
caught before merge rather than discovered later as a cross-tenant leak or an
unmaintainable dependency graph. Constitution Principle VII is the governing rule:
*anything that must always be true is enforced by a gate that fails the build; human
review does not scale and does not remember.*

## Inherited Requirements

Spec 001 explicitly deferred two requirements to this slice, with an instruction to
renumber on adoption. They are adopted here rather than restated loosely:

| Deferred from spec 001 | Original text | Adopted here as |
|---|---|---|
| `old-FR-028` | Enforce architectural boundaries automatically, such that a violating change fails the build | FR-004, FR-005, FR-008, FR-010, FR-012, FR-014, FR-015 (one gate per boundary) |
| `old-SC-008` | A deliberate architectural boundary violation is rejected by the automated gate 100% of the time | SC-001, SC-006 |

Spec 001's live FR-024 ("The domain layer MUST NOT depend on infrastructure concerns")
carries the note *"Automated enforcement of this boundary is S3; the code must satisfy it
now regardless."* That enforcement is FR-004/FR-005 below.

Of the four enforcement gaps recorded in [U12](../../docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs),
**two are assigned to this slice** and both are covered here:

| U12 gap | ADR | Covered by |
|---|---|---|
| Raw SQL or background job bypassing the tenant filter | ADR-013 | FR-010, FR-011, FR-012, FR-013 |
| Calling a non-Azure managed service / provider SDK from app code | ADR-001, ADR-008 | FR-014, FR-015, FR-016 |

The other two U12 gaps (portal infrastructure changes → ADR-012; `.claude/skills` symlink
→ ADR-016) are S7-assigned and remain out of scope.

## What Already Exists

S2's T089 shipped [`tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs`](../../tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs)
with five passing tests that already cover part of this slice's intent. This spec does
**not** re-specify them as new work. What they do and do not cover:

| Existing test | Covers | Gap this slice closes |
|---|---|---|
| `TenancyDomain_HasNoProjectReferences` | Domain has zero `<ProjectReference>` | Does not check `<PackageReference>` — see FR-004 |
| `TenancyApplication_OnlyReferencesDomain` | Application references only Domain | Same package-level blind spot — see FR-005/FR-006 |
| `TenancyInfrastructure_NeverReferencedByDomainOrApplication` | Inward dependency direction | Project-level only |
| `OnlyTenancyApi_ReferencesInfrastructureDirectly` | Composition root is the only infra referencer | Only scans `src/`; no cross-capability rule for future projects — see FR-008 |
| `NoCapabilityOtherThanTenancyExistsUnderSrc` | Pins the one-capability fact | Self-described as "a documented snapshot, not an enforced rule" |

**The package-level blind spot is not hypothetical.** `Tenancy.Application.csproj` today
carries `<PackageReference Include="Microsoft.EntityFrameworkCore" />`, and the existing
tests pass anyway because they read only `<ProjectReference>` elements. This slice closes
that hole (FR-005) and resolves the violation it exposes (FR-006).

The violation is wider than that package reference's own comment claims. The comment says
the dependency exists "only for the `DbUpdateException` type used by
`EnsureUserProvisioned`" — that is stale. `DbUpdateException` is named in three places
inside `Tenancy.Application`:

| Location | Kind | Test coverage today |
|---|---|---|
| `Users/EnsureUserProvisioned.cs:73` | `catch (DbUpdateException)` — get-or-create race | **None.** No dedicated test file exists; the method's own doc comment admits "no integration test harness yet" |
| `Invitations/InviteMember.cs:129` | `catch (DbUpdateException)` — duplicate-invite race | Covered — `InviteMemberTests.cs:176` injects a `DbUpdateException` via a fake repository |
| `Abstractions/IInvitationRepository.cs:62` | `<exception cref="...DbUpdateException">` doc reference | N/A (documentation) |

This asymmetry sets the work order. `InviteMember`'s translation path can be refactored
against a test that already proves it works. `EnsureUserProvisioned`'s cannot — that path
has never been exercised, so refactoring it first would be changing untested code and
calling the result verified. FR-007 requires the missing test to be written and seen to
pass against today's behaviour *before* FR-006 touches that catch block.

## Foundational Work

These are prerequisites to the user stories, not user value in themselves:

- The project's own testing standard places architecture tests in
  `tests/ArchitectureTests/`. They currently live inside `tests/Tenancy.UnitTests/`,
  which is the wrong project — a unit-test project for domain/application logic with no
  I/O. Creating the correct project and migrating the five existing tests is FR-001/FR-002.
- The standard test layout also names `ContractTests/` and `EndToEndTests/`. Neither is
  created in this slice: the first real contract test belongs to S9 and end-to-end tests
  to S7+, and creating an empty project ahead of its first consumer is scaffolding without
  content. This exclusion is FR-003, recorded so it reads as a decision rather than an
  oversight.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A layering violation is caught at package level, not just project level (Priority: P1)

A developer working in `Tenancy.Domain` or `Tenancy.Application` reaches for something
from infrastructure — an EF Core type, an Azure SDK client, an ASP.NET Core abstraction —
and adds a NuGet package reference to get it. No project reference is involved, so
today's tests stay green and the layering erodes silently.

Resolving this also requires fixing the one instance that already exists:
`Tenancy.Application`'s dependency on `Microsoft.EntityFrameworkCore`. The decision taken
at review (2026-08-15) is to **forbid it and invert the dependency** rather than
allow-list it — `Infrastructure` catches EF Core's `DbUpdateException` and translates it
into a type owned by `Application`/`Domain`, so `Application` no longer names an EF Core
type at all. This is the architecture skill's rule 3 applied literally: *if the domain
needs something from infrastructure, invert it.*

**Why this priority**: Clean Architecture's entire value proposition — domain logic that
outlives any particular database or framework — collapses the first time this is violated
unnoticed, and ADR-013's tenant-isolation guarantee is built on this separation holding.
It is P1 both because it guards code that exists today and because it has a live
violation to clear.

**Independent Test**: Add a throwaway `<PackageReference Include="Microsoft.EntityFrameworkCore" />`
to `Tenancy.Domain`, run the suite, confirm it fails naming that package and project,
then discard.

**Acceptance Scenarios**:

1. **Given** `Tenancy.Domain`'s current dependency set (empty), **When** the gate runs,
   **Then** it passes.
2. **Given** a package reference to `Microsoft.EntityFrameworkCore`, any `Azure.*`
   package, or `Microsoft.AspNetCore.*` added to `Tenancy.Domain`, **When** the gate runs,
   **Then** it fails naming the offending package and project.
3. **Given** the same addition to `Tenancy.Application`, **When** the gate runs, **Then**
   it fails the same way.
4. **Given** `Tenancy.Application`'s EF Core dependency has been inverted per FR-006,
   **When** the gate runs, **Then** it passes with no allow-list entry required.
5. **Given** the inversion in FR-006, **When** `EnsureUserProvisioned`'s existing
   get-or-create race tests run, **Then** they still pass — the concurrent-provisioning
   behaviour is unchanged, only where the exception is translated.

---

### User Story 2 - Raw SQL cannot escape the audited allow-list (Priority: P1)

A developer adds an EF Core `FromSqlRaw`, `ExecuteSqlRaw`, `ExecuteSqlInterpolatedAsync`,
or equivalent call somewhere convenient, bypassing the tenant-scoping global query filter
that every LINQ query receives automatically under ADR-013. Exactly one such call exists
today by design — `MembershipRepository.RemoveMembershipAsync`'s `UPDLOCK, HOLDLOCK` row
lock, the sole audited exception named in spec 001's research.md R3.

**Why this priority**: U12 calls this "the serious one" — the most plausible route to a
cross-tenant leak under ADR-013's model, because it bypasses the one protection every
other query gets for free. P1 despite the existing instance being correct: the gate exists
to catch the *next*, unreviewed one.

**Independent Test**: Add a throwaway `ExecuteSqlRaw` call in a repository not on the
allow-list, run the suite, confirm it fails naming the new call site, then discard.

**Acceptance Scenarios**:

1. **Given** the one audited raw-SQL call, **When** the gate runs, **Then** it passes and
   the allow-list names that call site by file and member.
2. **Given** a second, undeclared raw-SQL call added anywhere in the solution, **When**
   the gate runs, **Then** it fails naming the new call site.
3. **Given** the audited call is moved to a different type or renamed without updating the
   allow-list, **When** the gate runs, **Then** it fails — the allow-list binds to file
   *and* member, so relocation is a visible diff rather than a silent pass.

---

### User Story 3 - A cross-capability data reach is caught before merge (Priority: P1)

Only `Tenancy` exists today, but S9 adds `Integration` and S11 `Delivery`, each owning its
own database per ADR-003. A developer building the second capability writes a repository
or query that reaches into Tenancy's store or `TenancyDbContext` directly instead of
holding a `TenantId` as a value.

**Why this priority**: This is the same defect class T060 caught by hand during S2 (a live
cross-tenant read) raised one level: cross-*capability* instead of cross-*tenant*. Writing
the gate before the second capability exists means the first violation is a build failure
rather than an incident.

**Independent Test**: Add a throwaway project outside the `Tenancy.*` family that
references `Tenancy.Infrastructure`, run the suite, confirm it fails, then discard.

**Acceptance Scenarios**:

1. **Given** `Tenancy` is the only capability, **When** the gate runs, **Then** it passes
   and pins that fact, so adding a second capability is a deliberate, visible act that
   forces this gate to be extended rather than silently satisfied.
2. **Given** a project outside `Tenancy.*` that references `Tenancy.Infrastructure` or
   names `TenancyDbContext` or any Tenancy persistence type, **When** the gate runs,
   **Then** it fails naming the offending project and reference.

---

### User Story 4 - A background job cannot touch tenant data without establishing context (Priority: P2)

No `IHostedService` or `BackgroundService` exists in the codebase today (verified:
zero occurrences across `src/` and `tests/`). The danger arrives with the first one — a
job iterating tenants or reacting to an event that queries tenant-scoped data without
first establishing tenant context bypasses the same protection User Story 2 defends, from
the opposite direction: missing context rather than bypassed filter.

The gate must be structural rather than heuristic. Asserting that a job type "also
contains a call that sets tenant context" false-positives when the job delegates to a
helper, and false-negatives when context is set after the first query. Instead, jobs are
forbidden from reaching tenant-scoped data access directly at all, and must obtain it
through a sanctioned abstraction whose own contract is to establish tenant context first.

**Why this priority**: P2, not P1, because the code class it guards does not exist yet —
unlike User Stories 1-3, which guard code shipped in S2. It belongs in this slice anyway
because U12 assigns it here, and because defining the sanctioned path before the first job
is written is far cheaper than retrofitting it around three existing jobs later.

**Independent Test**: Add a throwaway `BackgroundService` that injects
`TenancyDbContext` directly, run the suite, confirm it fails naming the type, then
discard.

**Acceptance Scenarios**:

1. **Given** no background job exists, **When** the gate runs, **Then** it passes and pins
   that fact.
2. **Given** a type implementing `IHostedService` or deriving from `BackgroundService`
   that depends on `TenancyDbContext` or a tenant-scoped repository directly, **When** the
   gate runs, **Then** it fails naming that type.
3. **Given** a background job that obtains tenant-scoped data access only through the
   sanctioned tenant-context-establishing abstraction, **When** the gate runs, **Then** it
   passes.

---

### User Story 5 - No business code can reach a model provider SDK or hardcode a model name (Priority: P2)

The AI Platform capability does not exist until S13, and no provider SDK is referenced
anywhere today. ADR-008 stages the AI gateway with a capability-based seam; ADR-009
requires callers to ask for a capability (`ReleaseRiskAnalysis`) rather than name a model.
The project's testing standard lists both as required gates in this slice, and calls
ADR-008's the **load-bearing** one — the seam is worthless if business code can simply
bypass it.

**Why this priority**: P2 for the same reason as User Story 4 — it guards code that does
not exist yet. Included here rather than deferred to S13 because deferring a gate until
the code it governs exists is precisely the failure mode U12 documents: by then the
violation is already shipped and the gate becomes a refactoring project instead of a
guardrail.

**Independent Test**: Add a throwaway provider-SDK package reference (or a hardcoded model
name string) to `Tenancy.Application`, run the suite, confirm it fails, then discard.

**Acceptance Scenarios**:

1. **Given** no provider SDK is referenced anywhere, **When** the gate runs, **Then** it
   passes and pins that fact, so S13's first provider reference must be a deliberate
   change to this gate's allow-list.
2. **Given** a model provider SDK package referenced by any assembly other than the
   future AI Platform capability, **When** the gate runs, **Then** it fails naming the
   assembly and package.
3. **Given** a model identifier string appearing outside AI Platform configuration,
   **When** the gate runs, **Then** it fails naming the location.

---

### User Story 6 - No requirement in spec 001 can silently lose its test coverage (Priority: P3)

S2's T089 hand-audited all 26 functional requirements in spec 001 into `coverage.md`'s
FR→test matrix. That audit is a point-in-time artifact: a covering test deleted or renamed
tomorrow leaves the matrix stale and nobody finds out until someone redoes the audit by
hand.

The mapping must be machine-readable by construction rather than parsed out of
`coverage.md`'s prose. That file cites tests inconsistently — some with paths, some as
`File.cs.MethodName`, some as counts like "(4 tests)" — and a gate that parses it would
produce false failures, which is how a gate loses the team's trust and gets disabled.
Instead each covering test declares the requirement it covers, and the gate asserts every
requirement has at least one declaring test.

**Why this priority**: P3, the lowest here, because `coverage.md` exists and is current;
this story prevents regression rather than closing a live gap.

**Independent Test**: Remove the coverage declaration from the only test covering one
requirement, run the suite, confirm it fails naming that requirement, then restore.

**Acceptance Scenarios**:

1. **Given** every requirement FR-001 through FR-026 of spec 001 has at least one test
   declaring that it covers it, **When** the gate runs, **Then** it passes.
2. **Given** the last test declaring coverage for one requirement is deleted or its
   declaration removed, **When** the gate runs, **Then** it fails naming that specific
   requirement.
3. **Given** a declaration naming a requirement identifier that does not exist in spec
   001, **When** the gate runs, **Then** it fails — a typo must not silently satisfy a
   different requirement or none at all.

---

### Edge Cases

- **A capability legitimately needs a shared, non-domain library** (a logging
  abstraction, a result type). Out of scope: FR-004/FR-005 name a specific forbidden set
  (EF Core, `Azure.*`, ASP.NET Core), not an allow-list of every permitted package.
- **The audited raw-SQL exception is modified, moved, or renamed.** Must fail the gate
  (FR-011) — the allow-list binds file *and* member precisely so this is visible.
- **A future capability legitimately needs another's data.** ADR-003 already answers
  this: hold the identifier as a value, project the data into the reading context, never
  join across the boundary. This slice forbids only the unreviewed form — a direct
  reference with no interface at all — and does not attempt to pre-approve the legitimate
  form, which is S9's decision to make with a real consumer in hand.
- **S13 adds the first legitimate provider SDK reference.** FR-016's pin fails, which is
  the intended behaviour: extending the allow-list to name the AI Platform assembly is a
  reviewable diff.
- **The suite's runtime creeps as gates are added.** FR-021/SC-005 keep it bounded. S2's
  measured baseline is ~21s against a 5-minute bar, so the headroom is large — but these
  new gates must be included in the next measurement, not treated as free.
- **A gate is written that could never fail.** Explicitly guarded by FR-019: every gate in
  this slice must be demonstrated red before being accepted green.

## Requirements *(mandatory)*

### Functional Requirements

**Test project structure**

- **FR-001**: A dedicated architecture-test project MUST exist at `tests/ArchitectureTests/`,
  and every gate specified below MUST live in it rather than in the unit-test project.
- **FR-002**: The five existing tests in `tests/Tenancy.UnitTests/Architecture/` MUST be
  migrated into that project with no loss of coverage — each assertion they make today
  MUST still be made after migration.
- **FR-003**: `ContractTests/` and `EndToEndTests/` MUST NOT be created in this slice;
  their first real consumers are S9 and S7 respectively.

**Layering (adopts `old-FR-028`; enforces spec 001 FR-024)**

- **FR-004**: The build MUST fail when `Tenancy.Domain` depends on `Microsoft.EntityFrameworkCore`,
  any `Azure.*` package, or `Microsoft.AspNetCore.*` — whether by project reference or by
  package reference.
- **FR-005**: The build MUST fail when `Tenancy.Application` depends on any of the same
  set, by either reference kind.
- **FR-006**: `Tenancy.Application`'s `Microsoft.EntityFrameworkCore` package reference
  MUST be removed. EF Core's `DbUpdateException` MUST be translated at the
  `Infrastructure` boundary into a type owned by `Application` or `Domain`, and all three
  references to it inside `Tenancy.Application` — `EnsureUserProvisioned.cs`'s catch,
  `InviteMember.cs`'s catch, and `IInvitationRepository.cs`'s `<exception>` doc reference
  — MUST be updated to the translated type. The stale comment on the package reference
  MUST be removed with the reference itself.
- **FR-007**: Both of FR-006's translation paths MUST be under test before and after the
  change:
  - **(a)** `EnsureUserProvisioned`'s get-or-create race has no test today. A test
    exercising it MUST be written and seen to pass against the current
    `DbUpdateException`-based behaviour *before* FR-006 alters that catch block —
    refactoring first would mean changing untested code and reporting the result as
    verified.
  - **(b)** `InviteMemberTests`' existing duplicate-invite race test MUST continue to
    prove the same behaviour afterwards, updated to inject the translated exception type
    rather than `DbUpdateException`. Its assertion — that the race yields the same conflict
    signal as the pre-check — MUST NOT weaken.
- **FR-008**: The build MUST fail when any project outside the `Tenancy.*` family
  references `Tenancy.Infrastructure` or names `TenancyDbContext` or any Tenancy
  persistence type.
- **FR-009**: The build MUST pass today recording that `Tenancy` is the only capability,
  such that adding a second one forces this gate to be extended rather than silently
  satisfied.

**Raw SQL (adopts U12/ADR-013)**

- **FR-010**: The build MUST fail when a raw-SQL construct (`FromSqlRaw`,
  `FromSqlInterpolated`, `ExecuteSqlRaw`, `ExecuteSqlInterpolated`, their async forms, or
  equivalent) appears at a call site not on an explicit allow-list.
- **FR-011**: That allow-list MUST identify each entry by file **and** member, so moving
  or renaming an audited call site fails the gate until the allow-list is updated.

**Background jobs (adopts U12/ADR-013)**

- **FR-012**: The build MUST fail when a type implementing `IHostedService` or deriving
  from `BackgroundService` depends on `TenancyDbContext` or a tenant-scoped repository
  directly, rather than obtaining tenant-scoped data access through an abstraction whose
  contract establishes tenant context first.
- **FR-013**: The build MUST pass today recording that no such type exists yet.

**Provider SDK and model naming (adopts U12/ADR-001, ADR-008, ADR-009)**

- **FR-014**: The build MUST fail when any assembly other than the AI Platform capability
  references a model provider SDK.
- **FR-015**: The build MUST fail when a model identifier string appears outside AI
  Platform configuration.
- **FR-016**: The build MUST pass today recording that no provider SDK is referenced and
  no AI Platform capability exists yet.

**Requirement coverage (roadmap S3 "every FR in spec 001 maps to a test")**

- **FR-017**: Every functional requirement FR-001 through FR-026 of spec 001 MUST have at
  least one test that declares, in a machine-readable form attached to the test itself,
  that it covers that requirement.
- **FR-018**: The gate MUST fail, naming the specific requirement, when no declaring test
  remains for it.
- **FR-019**: The gate MUST fail when a declaration names a requirement identifier absent
  from spec 001.

**Gate quality**

- **FR-020**: Every gate specified in FR-004, FR-005, FR-008, FR-010, FR-012, FR-014,
  FR-015, and FR-017 MUST be demonstrated to fail against a deliberately introduced
  violation before being accepted, and that demonstration MUST be recorded.
- **FR-021**: Every failure produced by those gates MUST name the specific offending
  project, package, call site, type, or requirement — a bare pass/fail is not actionable.
- **FR-022**: The full test suite (unit, integration, and architecture together) MUST
  complete unattended in under 5 minutes.

### Key Entities

- **Capability**: A bounded context owning its data exclusively (ADR-003). Today:
  `Tenancy`, comprising `Tenancy.Domain`, `Tenancy.Application`, `Tenancy.Infrastructure`,
  `Tenancy.Api`. Future: `Integration` (S9), `Delivery` (S11), `AI Platform` (S13).
- **Audited raw-SQL allow-list**: The reviewable record of every raw-SQL call site
  permitted to bypass the tenant-scoping query filter, keyed by file and member.
- **Requirement coverage declaration**: The machine-readable marker attached to a test
  naming the spec 001 requirement it covers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the eight gates named in FR-020 rejects a deliberately introduced
  violation, demonstrated once per gate, with the failure output naming the offending
  location — 100% of gates proven capable of failing, none accepted on a first-run green.
- **SC-002**: `Tenancy.Domain` and `Tenancy.Application` depend on zero infrastructure
  packages, with no allow-list exception required for either.
- **SC-003**: All 26 functional requirements of spec 001 resolve to at least one declaring
  test, with zero requirements able to lose coverage without the build failing.
- **SC-004**: Every S2 test that passed before this slice still passes after it, and the
  two race-translation paths FR-006 touches are both covered by a test that has been seen
  to pass against the pre-refactor behaviour — one newly written
  (`EnsureUserProvisioned`), one already existing (`InviteMember`). Net test count for
  these paths goes up by one, never down.
- **SC-005**: The full suite completes unattended in under 5 minutes, and the new
  runtime is measured and recorded rather than assumed from S2's ~21-second baseline.
- **SC-006**: A developer who introduces any guarded violation learns the exact offending
  location from the failure output alone, without asking another person what broke.

## Assumptions

- The five existing `CapabilityBoundaryTests` are correct in what they assert and are
  migrated rather than rewritten; this slice widens their scope (package-level, cross
  capability) rather than revisiting their conclusions.
- `Tenancy.Application`'s EF Core dependency is the only existing layering violation.
  This was checked, not assumed: `Tenancy.Domain` has zero project *and* package
  references, and no `Azure.*` or `Microsoft.AspNetCore.*` package is referenced by either
  inner layer (verified against `Directory.Packages.props`, which centralises all versions).
  If the package-level gate reveals others once written, they are in scope for this slice
  under FR-006's rationale rather than deferred.
- No model provider SDK is referenced anywhere in the solution today — verified against
  the full central package list, whose thirteen entries are all EF Core, ASP.NET Core,
  Microsoft.Identity.Web, or test infrastructure. FR-016's pin therefore records a checked
  fact rather than an assumed one.
- No AI Platform capability, provider SDK, background job, or second capability exists
  during this slice, so FR-009, FR-013, and FR-016's gates pin absence rather than
  validate real instances. Each is written so the first real instance forces a visible
  change to the gate.
- "Model provider SDK" and "model identifier string" are given concrete, enumerable
  definitions during planning; specifying the exact package and pattern list is an
  implementation decision, not a requirement.

## Revision Notes

Revised 2026-08-15 following a pre-plan review that found eight issues in the first draft.
Recorded here because several were errors of overclaiming, and the corrections changed
this slice's scope:

1. **US1 presented already-shipped work as new.** S2's T089 had already implemented five
   layering tests. Added the [What Already Exists](#what-already-exists) section and
   re-scoped US1 to the genuine gap.
2. **The genuine gap was missed entirely**: the existing tests read only
   `<ProjectReference>`, and `Tenancy.Application` already violates the layering rule via
   a `<PackageReference>`. FR-004/FR-005 now check both reference kinds; FR-006 clears the
   live violation. Decision taken at review: invert the dependency rather than allow-list
   it.
3. **Two required S3 gates were absent**: ADR-008's provider-SDK gate (the project's
   testing standard calls it load-bearing) and ADR-009's model-name gate. Added as User
   Story 5 / FR-014-FR-016. Decision taken at review: implement in S3, not deferred to S13.
4. **Test project location was wrong and unaddressed** — architecture tests belong in
   `tests/ArchitectureTests/`, not inside the unit-test project. Added FR-001/FR-002, plus
   FR-003 to record deliberately *not* scaffolding `ContractTests/`/`EndToEndTests/`.
5. **The coverage gate was specified against a fragile source.** Parsing `coverage.md`'s
   inconsistent prose would generate false failures; replaced with per-test declarations
   (FR-017-FR-019).
6. **The background-job rule was a naive heuristic** ("sets context in the same type"),
   which false-positives on delegation and false-negatives on ordering. Replaced with a
   structural rule: jobs may not reach tenant-scoped data access directly at all (FR-012).
7. **No requirement that gates be proven able to fail**, despite the testing standard
   naming that as a red flag. Added FR-020 and SC-001.
8. **Inherited requirements were not traced.** Spec 001 explicitly deferred `old-FR-028`
   and `old-SC-008` here; added the [Inherited Requirements](#inherited-requirements)
   mapping.

A second verification pass against the codebase then caught two errors introduced by the
first revision itself:

9. **The revision overclaimed test coverage.** It asserted that "existing behavioural tests
   covering `EnsureUserProvisioned`'s concurrent-provisioning race MUST still pass" — no
   such tests exist. There is no dedicated test file for that use case, and the method's
   own doc comment concedes "no integration test harness yet". FR-007 now requires writing
   that test red-first *before* the refactor, and SC-004 no longer claims to preserve
   something that was never there. This was the same class of error the review was
   convened to find, reproduced one draft later.
10. **The refactor's scope was understated.** The package reference's comment claims it
    exists "only for `EnsureUserProvisioned`", which is stale: `InviteMember.cs` also
    catches `DbUpdateException`, and `IInvitationRepository.cs` names it in an
    `<exception>` doc reference. FR-006 now covers all three sites plus the stale comment,
    and the [What Already Exists](#what-already-exists) table records which of the two
    catch paths is tested — which is what sets the work order in FR-007.
