# Feature Specification: Architecture Tests

> **Historical — multi-tenancy was removed on 2026-10-23** ([ADR-025](../../docs/adr/ADR-025-single-organization.md)). This spec describes the system as built at the time and is not rewritten. Where it says tenant, the current code has one organization per deployment, and the service is `src/Identity`. The tenant-isolation gates (`TenantIsolationGates`, the background-job tenant-context rationale) were removed or reworded with it.

**Feature Branch**: `002-architecture-tests`
**Created**: 2026-08-15
**Revised**: 2026-08-15 (pre-plan review — see [Revision Notes](#revision-notes))
**Status**: Draft
**Input**: User description: "S3 — Architecture tests. Per roadmap.md: enforce domain≠infrastructure layering, no cross-service data access, no provider SDK outside AI Platform boundary, raw SQL restricted to audited helpers, background jobs must set tenant context (U12, docs/traceability.md). Done when: a deliberate domain→infrastructure reference fails the build; a deliberate cross-service data access fails the build; every FR in spec 001 maps to a test; full suite runs unattended under 5 minutes. Builds on existing tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs from S2's T089."

This slice has no end user. Its "user" is the **developer working in this repository**(including a future AI agent) — the person whose accidental boundary violation must be caught before merge rather than discovered later as a cross-tenant leak or an unmaintainable dependency graph. Constitution Principle VII is the governing rule: *anything that must always be true is enforced by a gate that fails the build; human review does not scale and does not remember.*

## Clarifications

### Session 2026-08-15

- Q: FR-014/FR-017/FR-018 rest on package-name lists with "or equivalent" — how should the forbidden set be defined so an unlisted equivalent cannot bypass it? → A: Pin the solution's entire package set; any new package fails the gate until the pin is deliberately updated.
- Q: FR-012 requires background jobs to use "an abstraction whose contract establishes tenant context first", but no such abstraction exists — create the seam now, or enforce the prohibition only? → A: Prohibition only, with an actionable failure message; the sanctioned path is designed at S8/S10 when a real consumer fixes its shape.
- Q: Which types does FR-012's "tenant-scoped repository" cover? → A: `TenancyDbContext` plus every persistence port — identified mechanically as any port whose implementation lives in a persistence namespace, so ports added by S9/S11 are covered without curating a list. `ITenantContext` is excluded: it is not a persistence port and is what a job would legitimately use.
- Q: What counts as a "model identifier string" for FR-015, and over what scope? → A: A small explicit pattern list (`gpt-`, `claude-`, `gemini-`, `llama-`, `text-embedding-`, `o1-`) scanned over `src/**/*.cs` only — not docs, specs, or tests, which legitimately name models throughout.

### Session 2026-08-15 (checklist findings)

- Q: FR-012's structural gate cannot see a job that resolves data access at runtime — a `BackgroundService` is a singleton and must use `IServiceScopeFactory`, so constructor inspection is blind by construction. Expand the gate, or close the property another way? → A: Do not expand the gate. Add a runtime fail-closed guard instead (FR-027), which holds regardless of how the job obtained its context, and record FR-012's limits honestly.
- Q: Four `IgnoreQueryFilters` call sites are live and the spec gates none of them. Add a gate? → A: Yes — forbid the bare no-arg form, permit the named form (FR-026). No allow-list needed; all four existing sites already comply.

## Inherited Requirements

Spec 001 explicitly deferred two requirements to this slice, with an instruction to renumber on adoption. They are adopted here rather than restated loosely:

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
with five passing tests that already cover part of this slice's intent. This spec does **not** re-specify them as new work. What they do and do not cover:

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
forbidden from reaching tenant-scoped data access directly at all.

**No sanctioned replacement path is built in this slice** (clarified 2026-08-15). The
prohibition is the safety property and it applies today; the abstraction a job should use
instead does not exist, and its shape is genuinely unknown — the first real consumers are
S8's Service Bus subscriber and S10's scheduled sync, which need different
context-establishment shapes. Guessing now is the "shape guessed wrong before real
requirements exist" error the `architecture` skill warns about, and it would contradict
ADR-021. The gate therefore refuses the unsafe construction and tells the author to propose
a sanctioned path rather than silently blocking them.

**Why this priority**: P2, not P1, because the code class it guards does not exist yet —
unlike User Stories 1-3, which guard code shipped in S2. It belongs in this slice anyway
because U12 assigns it here, and because forbidding the unsafe construction before the first
job is written is far cheaper than retrofitting the rule around three existing jobs later.

**Independent Test**: Add a throwaway `BackgroundService` that injects
`TenancyDbContext` directly, run the suite, confirm it fails naming the type, then
discard.

**Acceptance Scenarios**:

1. **Given** no background job exists, **When** the gate runs, **Then** it passes and pins
   that fact.
2. **Given** a type implementing `IHostedService` or deriving from `BackgroundService`
   whose constructor takes `TenancyDbContext` or any persistence port, **When** the gate
   runs, **Then** it fails naming that type and the offending dependency.
3. **Given** such a job whose constructor takes only `ITenantContext`, **When** the gate
   runs, **Then** it passes — establishing tenant context is the sanctioned direction, not the
   violation. **Passing this gate does not make the job safe**: if it never actually sets the
   context and reaches data through a use case or a resolved scope, FR-027 is what refuses the
   write at runtime. FR-012 refuses the obvious mistake cheaply; it does not certify correctness.
4. **Given** a background job that takes no tenant-scoped data-access dependency at all,
   **When** the gate runs, **Then** it passes — the gate refuses the unsafe construction, it
   does not require a specific replacement.
5. **Given** the gate fails on such a job, **When** the developer reads the failure output,
   **Then** it names the offending type *and* states what to do instead, citing ADR-013 —
   a gate that blocks without guidance is one a developer disables.

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

1. **Given** every one of spec 001's twenty-six functional requirements (`001-FR-001` through `001-FR-026`) has at least one test
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
- **The suite's runtime creeps as gates are added.** FR-025/SC-005 keep it bounded. S2's
  measured baseline is ~21s against a 5-minute bar, so the headroom is large — but these
  new gates must be included in the next measurement, not treated as free.
- **A gate is written that could never fail.** Explicitly guarded by FR-023: every gate in
  this slice must be demonstrated red before being accepted green.

## Requirements *(mandatory)*

### Functional Requirements

**What "the build MUST fail" means in this slice.** Nine requirements below use that phrase.
CI does not exist until S7, so in this slice it means **`dotnet test` fails**: the gates are
ordinary tests, and enforcement depends on a developer running the suite. That is vigilance, not
a gate, and Constitution Principle VII prefers the opposite — so the gap is recorded as a
deferral to S7 rather than left implicit (see [Deferred Requirements](#deferred-requirements)).
The phrase is kept because it states the intended end condition, and re-verifying it costs
nothing once a pipeline exists.

**All gates scan `src/`, not `tests/`.** Test code legitimately does things production code must
not — raw SQL for fixture setup, a throwaway `BackgroundService` to prove a gate can fail — and
scanning it would make FR-013's absence pin and FR-023's proof obligation contradict each other
(CHK029). Proofs therefore add the violation to `src/` temporarily and revert it.

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
  equivalent) appears **under `src/`** at a call site not on an explicit allow-list. Test code is
  out of scope: a test may legitimately use raw SQL for fixture setup, and no test serves a
  tenant request.
- **FR-011**: That allow-list MUST identify each entry by file **and** member, so moving
  or renaming an audited call site fails the gate until the allow-list is updated.

**Background jobs (adopts U12/ADR-013)**

- **FR-012**: The build MUST fail when a type implementing `IHostedService` or deriving
  from `BackgroundService` declares a constructor dependency on `TenancyDbContext` or on any
  **persistence port**. A persistence port is identified mechanically — a port whose
  implementing type lives in a persistence namespace — rather than by a curated interface
  list, so ports introduced by S9's `Integration` and S11's `Delivery` capabilities are
  covered without anyone remembering to extend the gate (clarified 2026-08-15). Today that
  resolves to `ICreateTenantRepository`, `IMembershipDirectory`, `IMembershipRepository`,
  `IInvitationRepository`, `ITenantRepository`, and `IUserRepository`. **`ITenantContext` is
  excluded** — it is not a persistence port, and it is what a job would legitimately use to
  establish context. This slice specifies the prohibition only — **no sanctioned replacement
  abstraction is built** (clarified 2026-08-15), because its shape is fixed by the first real
  consumer at S8/S10, not by this slice. The gate's failure message MUST therefore state what
  to do instead and cite ADR-013, so the first background-job author is redirected rather than
  merely blocked.

  *Known limits, established by checklist review (CHK023-CHK025) and recorded rather than
  glossed:* this gate closes the **direct constructor route only**. It cannot see a job that
  resolves `TenancyDbContext` through `IServiceScopeFactory` — which a `BackgroundService`,
  being a singleton, is *required* to do — nor a job that depends on an Application use case
  instead of a port. No constructor-level gate can. FR-027 closes the underlying property at
  runtime, where those routes converge; FR-012 remains worthwhile because it refuses the
  obvious mistake at the cheapest possible point.
- **FR-013**: The build MUST pass today recording that no such type exists yet.

**Provider SDK and model naming (adopts U12/ADR-001, ADR-008, ADR-009)**

- **FR-014**: The build MUST fail when any assembly other than the AI Platform capability
  references a model provider SDK. Enforced through the **pinned dependency set** (see Key
  Entities) rather than a list of known provider names: a deny-list cannot enumerate
  "equivalent" packages, so an unlisted one would pass a green gate.
- **FR-015**: The build MUST fail when a model identifier string appears in production code.
  Scope and pattern set are fixed as follows (clarified 2026-08-15): the gate scans
  `src/**/*.cs` only, matching a small explicit pattern list — `gpt-`, `claude-`, `gemini-`,
  `llama-`, `text-embedding-`, `o1-`. **Docs, specs, and tests are deliberately out of scope**:
  this repository names models throughout its documentation and commit trailers, so a
  repo-wide scan would fail on its own prose the first time it ran. The "outside AI Platform
  configuration" exemption has no location to point at until S13 creates one; when it does,
  that path is added as the single allowed exception.

  *Acknowledged limitation*: FR-014's pinned dependency set already blocks the realistic path,
  since a model cannot be called without a provider SDK. A model name with no SDK present is
  an inert string. FR-015's remaining value is pinning that inertness, not preventing a live
  defect — recorded so a later reader does not overestimate what this gate buys.
- **FR-016**: The build MUST pass today recording that no provider SDK is referenced and
  no AI Platform capability exists yet.

**Application-layer patterns (enforces [ADR-021](../../docs/adr/ADR-021-application-layer-patterns-at-first-consumer.md))**

ADR-021 names this slice as the intended enforcement point for its rulings 1 and 2, so
those gates belong here. Its ruling 3 (no separate read model) is explicitly recorded there
as not mechanically checkable while one context exists, and is therefore *not* specified
below — reproducing it as a gate would be theatre.

- **FR-017**: The build MUST fail when a validation-library package (FluentValidation or
  equivalent) is referenced by any project, enforcing ADR-021 ruling 1. Enforced by the same
  pinned dependency set as FR-014.
- **FR-018**: The build MUST fail when a mediator/dispatcher package (MediatR or
  equivalent) is referenced by any project, enforcing ADR-021 ruling 2. Enforced by the same
  pinned dependency set as FR-014.
- **FR-019**: An unhandled `DomainException` MUST NOT reach a client as a `500`.
  `ProblemDetailsHandler` MUST map `DomainException` to `400` and `ConflictException` to
  `409` centrally, so that an endpoint which omits its own `catch` still produces a correct
  status. Existing endpoint-level mapping MUST continue to work unchanged. ADR-021 records
  this convention as a known weakness left load-bearing by its ruling 1; this closes it.

  *Amended by [research.md](research.md) R2.* The original wording required a gate that fails
  when an endpoint handler *can* surface a `DomainException` as `500`. That is a method-body
  dataflow question, answerable only by a Roslyn analyzer — disproportionate for one
  convention, and it would leave `ProblemDetailsHandler`'s blanket `500` as the underlying
  defect regardless. Removing the failure mode is the stronger form of Principle VII: a gate
  detects the mistake, central mapping means there is no mistake to detect. The
  client-visible guarantee is unchanged.

**Requirement coverage (roadmap S3 "every FR in spec 001 maps to a test")**

- **FR-020**: Every functional requirement of spec 001 — `001-FR-001` through `001-FR-026` — MUST have at
  least one test that declares, in a machine-readable form attached to the test itself,
  that it covers that requirement.

  *What this gate does and does not prove (CHK010).* It detects **loss** of declared coverage —
  a covering test deleted, renamed, or stripped of its declaration. It does **not** verify that a
  declaring test meaningfully exercises the requirement it names: a test declaring `FR-007` while
  asserting something unrelated satisfies this literally, so the gate is gameable by
  attribute-spraying. Verifying substance requires human judgement, which is what S2's T089 hand
  audit provided and what `coverage.md` records. This gate protects that audit from rotting; it
  does not replace it, and SC-003 should not be read as claiming otherwise.
- **FR-021**: The gate MUST fail, naming the specific requirement, when no declaring test
  remains for it.
- **FR-022**: The gate MUST fail when a declaration names a requirement identifier absent
  from spec 001.

**Gate quality**

- **FR-023**: Every gate specified in FR-004, FR-005, FR-008, FR-009, FR-010, FR-011, FR-012,
  FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019, FR-020, FR-026, and FR-027 —
  **seventeen in total, including the three absence pins** — MUST be demonstrated to
  fail against a deliberately introduced violation before being accepted, and that
  demonstration MUST be recorded. FR-019's proof takes a different form from the rest, since
  it is a behavioural guarantee rather than a structural gate: its test MUST be seen to fail
  against the current blanket-`500` behaviour before the central mapping is added. The three
  absence pins (FR-009, FR-013, FR-016) are included because FR-023's own rationale applies to
  them unchanged: a pin that would not notice the thing appearing is decoration. Their proof is
  the same exercise in reverse — introduce the capability, job, or provider SDK under `src/`,
  observe red, revert.
- **FR-024**: Every failure produced by those gates MUST name the specific offending
  project, package, call site, type, or requirement — a bare pass/fail is not actionable.
- **FR-025**: The full test suite (unit, integration, and architecture together) MUST
  complete unattended in under 5 minutes.

**Tenant-isolation defence in depth (added 2026-08-15 from checklist review)**

- **FR-026**: The build MUST fail when `IgnoreQueryFilters()` is called with **no arguments**
  anywhere under `src/`. The named form — `IgnoreQueryFilters(["TenantFilter"])` — MUST remain
  permitted. Spec 001's research R3 prohibits the bare form because it disables *every* filter,
  not only tenancy; T095 found and corrected three such calls by hand. Four call sites are live
  today and all already comply, so no allow-list is required — which is why this is a plain
  prohibition rather than an FR-010-style allow-list.
- **FR-027**: Inserting an `ITenantOwned` entity while no tenant context is established MUST be
  refused at runtime, not silently stamped with `default(TenantId)`. This closes the property
  FR-012's structural gate provably cannot reach.

  *Verified behaviour this rests on, rather than assumed:* `CurrentTenantId` is a non-nullable
  struct, so "unset" is `Guid.Empty`. Reads already fail closed (the filter matches no row) and
  update/delete already throw (original tenant differs from ambient). **Insert was the only
  direction that did not** — it produced a row owned by a tenant that does not exist. Note this
  makes the defect a silent orphan rather than a cross-tenant leak, so U12's framing of the
  background-job gap as *"the most plausible route to a cross-tenant leak"* **overstates it
  against this implementation**; recorded here rather than left for the next reader to
  rediscover.

  The two operations that legitimately insert a tenant-owned entity outside a tenant-scoped
  request — create-tenant and accept-invitation — already set the context first and both document
  why, so this requirement converts an existing convention into enforcement (Principle VII).

### Key Entities

- **Capability**: A bounded context owning its data exclusively (ADR-003). Today:
  `Tenancy`, comprising `Tenancy.Domain`, `Tenancy.Application`, `Tenancy.Infrastructure`,
  `Tenancy.Api`. Future: `Integration` (S9), `Delivery` (S11), `AI Platform` (S13).
- **Audited raw-SQL allow-list**: The reviewable record of every raw-SQL call site
  permitted to bypass the tenant-scoping query filter, keyed by file and member.
- **Requirement coverage declaration**: The machine-readable marker attached to a test
  naming the spec 001 requirement it covers.
- **Persistence port**: A port whose implementing type lives in a persistence namespace —
  the mechanical definition FR-012's gate uses instead of a curated interface list, chosen so
  that capabilities added later are covered automatically. Excludes `ITenantContext`, which
  carries no persistence implementation.
- **Pinned dependency set**: The recorded list of every NuGet package the solution may
  reference, checked against `Directory.Packages.props` (which already centralises all
  versions). Adding any package — a validation library, a mediator, a model provider SDK, or
  anything unrelated — fails the gate until the pin is updated, so no dependency decision can
  be made silently. Chosen over per-package deny-lists because "or equivalent" cannot be
  enumerated. **Accepted trade-off**: the pin is deliberately noisy, tripping on legitimate
  additions too; that cost buys the property that an unknown equivalent cannot slip past.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the seventeen gates named in FR-023 rejects a deliberately introduced
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

## Deferred Requirements

Spec 001 handed `old-FR-028` and `old-SC-008` to this slice through a table like this one, and
that mechanism is why they were not lost. This slice defers two things the same way, with the
receiving slice named. **Renumber on adoption.**

| Deferred | Requirement | Target slice |
|---|---|---|
| `old-FR-029` | The seventeen gates in FR-023 MUST run in the pipeline, so enforcement no longer depends on a developer choosing to run `dotnet test` (closes the Principle VII gap recorded above FR-001) | **S7** |
| `old-FR-030` | A background job MUST obtain tenant-scoped data access through a sanctioned abstraction that establishes tenant context; this slice specifies only the prohibition (FR-012) and a runtime backstop (FR-027), because the abstraction's shape is fixed by its first real consumer | **S8 / S10** |

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
   (FR-020-FR-022).
6. **The background-job rule was a naive heuristic** ("sets context in the same type"),
   which false-positives on delegation and false-negatives on ordering. Replaced with a
   structural rule: jobs may not reach tenant-scoped data access directly at all (FR-012).
7. **No requirement that gates be proven able to fail**, despite the testing standard
   naming that as a red flag. Added FR-023 and SC-001.
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

A third pass, after [ADR-021](../../docs/adr/ADR-021-application-layer-patterns-at-first-consumer.md)
was accepted, added the gates that ADR names this slice as responsible for:

11. **ADR-021 assigned enforcement to S3 and this spec did not know it.** The ADR's
    Compliance section states that adding its package-name checks to S3's gate set "is the
    intended enforcement". Since Principle II places ADRs above specs, the spec was out of
    date with respect to a higher-authority document that names it. Added FR-017 (no
    validation-library package), FR-018 (no mediator package), and FR-019 (`DomainException`
    must map to 4xx, closing the convention ADR-021 leaves load-bearing). Downstream
    requirements renumbered accordingly; FR-023's proof list and SC-001's count grew from
    eight gates to eleven. *(Later grown to seventeen — see notes 14-19.)*
12. **ADR-021's ruling 3 is deliberately not specified as a gate.** The ADR records that no
    separate read model exists and that this is not mechanically checkable while one context
    exists. Reproducing it as an architecture test would be a test that could never fail —
    the exact thing FR-023 exists to prevent.
13. **FR-019 was amended during planning, not silently rebuilt.** Research (R2) established
    that the structural form it originally required — a gate detecting an endpoint that *could*
    let a `DomainException` escape — needs method-body dataflow analysis, i.e. a Roslyn
    analyzer. Rather than build that, or quietly ship something weaker, the requirement was
    rewritten to remove the failure mode: `ProblemDetailsHandler` maps the exception types
    centrally, so a forgetful endpoint is harmless. The client-visible guarantee is identical.

A further item from that ADR was fixed outside this spec rather than folded into it: the
display-name length guard, where `TenantConfiguration` declared `HasMaxLength(200)` while the
domain checked only null/whitespace. That is an S2 domain defect, not architecture-test work, so
it was closed in its own commit (written red-first: two over-limit tests failed before the guard
was added), and `Tenant.DisplayNameMaxLength` is now the single source the schema derives from.

A fourth pass, `/speckit.checklist`, produced [gate-efficacy.md](checklists/gate-efficacy.md) and
[tenant-isolation.md](checklists/tenant-isolation.md) — 42 items. It found defects the three
earlier passes had all missed, because it asked a question none of them had: not "is this
consistent?" but "what would go wrong if this were built exactly as written?"

14. **FR-012's structural gate could not close the property it was written for.** A
    `BackgroundService` is a singleton and must resolve scoped services through
    `IServiceScopeFactory`, so constructor inspection is blind to it by construction (CHK024) —
    the gate was unclosable, not merely incomplete. Verification also corrected U12's premise:
    reads and update/delete already fail closed against an unset tenant; only *insert* did not,
    making the defect a silent orphan rather than a cross-tenant leak. **FR-027** closes it at
    runtime. FR-012 keeps its limits stated rather than implied.
15. **Four live `IgnoreQueryFilters` call sites, zero spec coverage** (CHK040) — more existing
    instances than raw SQL has, and T095 had already fixed three of them by hand. **FR-026** added.
16. **Five inter-document conflicts** (CHK002, 007, 029, 032, 042) resolved by deciding which side
    was right rather than by softening wording: the absence pins *do* need failure proofs (so
    FR-023 grew to sixteen), gates scan `src/` only (so proof fixtures in `tests/` cannot collide
    with absence pins), and "the build MUST fail" now has one definition plus an S7 deferral
    instead of nine unqualified claims.
17. **FR-020's coverage gate is gameable and now says so** (CHK010). It detects *loss* of declared
    coverage, not whether a declaring test meaningfully exercises its requirement. T089's hand
    audit remains the substantive evidence; this gate only stops it rotting.

A fifth pass, `/speckit.analyze`, cross-checked spec against plan against tasks once `tasks.md`
existed. Both of its substantive findings were consequences of decisions taken earlier in this
same document:

18. **A numbering hazard, caught by the analysis biting itself.** This spec's
    FR-026 and FR-027 collide with references to *spec 001's* FR-026 under substring matching. It
    is not hypothetical: the analyze pass mis-attributed FR-026's proof task because T041 contained
    the string `FR-001–FR-026 of spec 001`. The risk was raised when FR-026/FR-027 were appended
    and dismissed as manageable — wrongly. References to spec 001's requirements now carry a
    `001-` prefix, following the `old-FR-0NN` prefixing spec 001 itself uses for exactly this
    purpose. **Any tooling that greps requirement identifiers across these documents must treat a
    bare `FR-0NN` as belonging to spec 002.**
19. **FR-011 was proven in `quickstart.md` but absent from FR-023's list** — the same conflict as
    note 16's CHK002, incompletely fixed: the three absence pins were added, FR-011 was missed.
    quickstart was right again; detecting a relocated allow-list entry is a distinct provable
    behaviour. **FR-023 grew from sixteen to seventeen.**
