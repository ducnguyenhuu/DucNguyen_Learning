# Tasks: Architecture Tests (S3)

**Input**: Design documents from `/specs/002-architecture-tests/`
**Prerequisites**: [spec.md](spec.md) (27 FRs, 6 user stories), [plan.md](plan.md), [research.md](research.md), [quickstart.md](quickstart.md), [checklists/](checklists/)

**Tests**: Tests are not optional here — they **are** the deliverable. This slice ships seventeen
gates, which are ordinary xUnit tests. FR-023 additionally requires every gate to be demonstrated
red before acceptance, so each gate carries a paired proof task rather than a "write the test"
task followed by hope.

**Organization**: Grouped by user story, with one extra phase for requirements that postdate the
stories (see the note below Phase 2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1–US6 per spec.md. Setup, Foundational, Unowned, and Polish phases carry no label
- Exact file paths are given in every task

## Path Conventions

Single project. Gates live in `tests/ArchitectureTests/`; production changes touch
`src/Tenancy/*`. Paths follow [plan.md](plan.md)'s Source Code layout.

## ⚠️ Identifiers stop at this file

Task descriptions below cite `FR-0NN`, `SC-0NN`, and `CHK0NN` deliberately — traceability is
what a task list is for. **Do not carry those identifiers into code.** No `T017`, no `FR-023`,
no `CHK019` in a comment, an XML doc, a test name, or a failure message.

Write the *reasoning* the identifier stands for instead. A reader six months from now cannot
resolve `CHK019`, and cannot tell whether a comment citing it is still true — `specs/` is
working material for one slice, not a permanent reference. ADR citations are the exception:
ADRs are permanent and live in `docs/adr/`.

```csharp
// Wrong
// Scoped to src/ only, per FR-010 — tests may legitimately use raw SQL (CHK032).

// Right
// Scoped to src/ only: test code may legitimately use raw SQL for fixture setup, and no
// test serves a tenant request, so scanning it would produce failures with nothing to fix.
```

This applies to failure messages too. A gate that fails with "violates FR-004" tells a
developer nothing; one that names the offending project and package tells them everything.

---

## Requirements with no owning user story

Five requirements were added after the six user stories were written — FR-017/FR-018/FR-019 when
[ADR-021](../../docs/adr/ADR-021-application-layer-patterns-at-first-consumer.md) was accepted, and
FR-026/FR-027 by the checklist review. They have no story to sit under, so **Phase 9** owns them
and carries no `[Story]` label.

This is recorded rather than papered over: it means spec.md's user stories no longer cover its full
requirement set. Adding a seventh story would be the tidier fix, and is deliberately *not* done
here because renumbering stories after planning costs more than the inconsistency does. Worth
correcting at the next slice's specify step, not retrofitting into this one.

**Already complete**: FR-027 landed in commit `3aebea6` (runtime fail-closed guard plus
`UnsetTenantContextWriteTests`), written red-first. Its task below is checked off with that
reference rather than re-listed as pending work.

---

## Phase 1: Setup

**Purpose**: Create the project the gates live in. FR-001/FR-003.

- [x] T001 (FR-001) Create `tests/ArchitectureTests/ArchitectureTests.csproj` targeting `net10.0`, referencing `xunit.v3` and `AwesomeAssertions` from `Directory.Packages.props` with no new package versions added
- [x] T002 Add project references from `tests/ArchitectureTests/ArchitectureTests.csproj` to all four `src/Tenancy/*` projects, and add the project to the solution file
- [x] T003 Add `tests/ArchitectureTests/AssemblyInfo.cs` with `[assembly: CollectionBehavior(DisableTestParallelization = true)]`, matching `Tenancy.IntegrationTests`' existing setting, since gates read shared files from disk
- [x] T004 Record in `tests/ArchitectureTests/README.md` that `ContractTests/` and `EndToEndTests/` are deliberately absent, naming roadmap slices S9 and S7 as their first consumers, so a later reader does not create them speculatively. State the reason, not the requirement number — roadmap slice names are permanent, `FR-003` is not (FR-003)

**Checkpoint**: An empty gate project builds and runs under `dotnet test`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No gate task can begin until this phase is complete — every gate uses these
helpers, and the migration must land before new gates are added alongside it.

- [x] T005 Create `tests/ArchitectureTests/Support/ProjectFile.cs` exposing project-reference and package-reference readers over `src/**/*.csproj` plus `Directory.Packages.props`, replacing the private `XDocument` helpers currently inside `CapabilityBoundaryTests`
- [x] T006 [P] Create `tests/ArchitectureTests/Support/SourceScanner.cs` that enumerates `.cs` files under `src/` only — excluding `bin/`, `obj/`, and `.git/` — and reports each match as file path plus enclosing member name, since FR-011 requires both
- [x] T007 [P] Create `tests/ArchitectureTests/Support/RepoRoot.cs` by lifting `CapabilityBoundaryTests.FindRepoRoot()` unchanged, so the depth-independent walk is shared rather than duplicated
- [x] T008 Migrate all five tests from `tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs` into `tests/ArchitectureTests/CapabilityBoundaryGates.cs`, preserving every assertion, then delete the original file and its now-empty `Architecture/` folder (FR-002)
- [x] T009 Verify FR-002's "no loss of coverage" concretely: record the five migrated test names and their assertion counts in the PR description, and confirm `dotnet test` reports the same total as before the move — this answers CHK019, which flagged that "no loss of coverage" named no verification mechanism
- [x] T010 (FR-023, SC-001) Decide and document where FR-023's failure demonstrations are recorded — resolving CHK001, which found the requirement says "MUST be recorded" without naming an artifact. Record the decision in `specs/002-architecture-tests/quickstart.md` §2 and use it consistently for every proof task below

**Checkpoint**: Shared helpers exist, the five S2 gates run from their correct home, and there is
one agreed place to record proofs.

---

## Phase 3: User Story 1 — Layering caught at package level (Priority: P1) 🎯 MVP

**Goal**: `Tenancy.Domain` and `Tenancy.Application` cannot depend on EF Core, Azure, or ASP.NET
Core by *either* reference kind — and the one live violation is cleared.

**Independent Test**: Add `<PackageReference Include="Microsoft.EntityFrameworkCore" />` to
`Tenancy.Domain.csproj`, run the suite, confirm it fails naming project and package, revert.

**⚠️ Order is forced here.** T011 must precede T012: `EnsureUserProvisioned`'s race path has no
test today, so refactoring it first would mean changing untested code and reporting the result as
verified. T014 must follow T012, or the gate is red for the whole slice.

- [ ] T011 [US1] Write `tests/Tenancy.UnitTests/Users/EnsureUserProvisionedTests.cs` covering the get-or-create race — inject a `DbUpdateException` via a fake `IUserRepository`, assert the existing row is returned — and **run it green against today's `DbUpdateException` behaviour before touching any production code** (FR-007a)
- [ ] T012 [US1] Add an `Application`-owned concurrency-conflict exception type in `src/Tenancy/Tenancy.Application/Abstractions/`, and translate EF Core's `DbUpdateException` into it at the `Infrastructure` boundary in `src/Tenancy/Tenancy.Infrastructure/Persistence/UserRepository.cs` and `InvitationRepository.cs` (FR-006)
- [ ] T013 [US1] (SC-002) Replace all three `Tenancy.Application` references to `DbUpdateException` with the translated type — `Users/EnsureUserProvisioned.cs:73`, `Invitations/InviteMember.cs:129`, and `Abstractions/IInvitationRepository.cs:62`'s `<exception>` doc — then remove the `<PackageReference Include="Microsoft.EntityFrameworkCore" />` and its now-false comment from `Tenancy.Application.csproj` (FR-006)
- [ ] T014 [US1] Update `tests/Tenancy.UnitTests/Invitations/InviteMemberTests.cs:176` to inject the translated exception type instead of `DbUpdateException`, keeping its assertion that the race yields the same conflict signal as the pre-check (FR-007b)
- [ ] T015 [US1] Implement the FR-004 gate in `tests/ArchitectureTests/LayeringGates.cs`: assert `Tenancy.Domain` declares no project or package reference to `Microsoft.EntityFrameworkCore`, `Azure.*`, or `Microsoft.AspNetCore.*`, failing with the offending project and package named (FR-024)
- [ ] T016 [US1] Implement the FR-005 gate in the same file for `Tenancy.Application`, over both reference kinds
- [ ] T017 [US1] Prove T015 and T016 red per FR-023: add each forbidden package to each project in turn, confirm failure output names project and package, revert, and record the demonstrations in the artifact chosen at T010
- [ ] T018 [US1] Run the full suite and confirm 197 pre-existing tests still pass alongside the new ones — FR-006 touches the auth path, so SC-004 requires no S2 regression

**Checkpoint**: Layering is enforced at package level and `Tenancy.Application` is clean, with the
EF Core dependency inverted rather than allow-listed.

---

## Phase 4: User Story 2 — Raw SQL confined to an audited allow-list (Priority: P1)

**Goal**: No raw-SQL call can be added under `src/` without a deliberate, reviewable allow-list
entry keyed by file and member.

**Independent Test**: Add `ExecuteSqlRaw("SELECT 1")` to a repository not on the allow-list, run
the suite, confirm it fails naming file and member, revert.

- [ ] T019 [US2] Define the allow-list's location and format in `tests/ArchitectureTests/RawSqlGates.cs` — a checked-in collection of (relative file path, member name) pairs seeded with the single audited entry, `Persistence/MembershipRepository.cs` / `RemoveMembershipAsync`. Resolves CHK036, which found FR-011 fixed the key but not where the list lives
- [ ] T020 [US2] Define what "member" means for the allow-list key and document the choice inline — resolving CHK033, which noted overloads, local functions, and lambdas are all plausibly "the member" and are not interchangeable for catching relocation
- [ ] T021 [US2] Implement the FR-010 gate using `Support/SourceScanner`, matching `FromSqlRaw`, `FromSqlInterpolated`, `ExecuteSqlRaw`, `ExecuteSqlInterpolated`, their async forms, and `Database.SqlQuery`, scoped to `src/` per the spec's stated scope
- [ ] T022 [US2] Require a justification comment adjacent to each allow-list entry and assert its presence, so adding an entry cannot be a silent one-line diff — resolving CHK034, which observed nothing made "audited" mean anything
- [ ] T023 [US2] Prove T021 red twice per FR-023: once by adding an unlisted raw-SQL call, and once by moving the audited call to a new method without updating the allow-list (FR-011's relocation case — FR-023 now names FR-011 explicitly, per analyze finding I1). Record both
- [ ] T024 [US2] Record in `RawSqlGates.cs` remarks that source-text matching is formatting-sensitive — a call split across lines or reached through an alias can evade it — and that the escalation path is a Roslyn analyzer rather than a looser regex. Write the reasoning, not a pointer to research.md (research.md R4)

**Checkpoint**: Raw SQL is gated, and the one legitimate exception is visible and justified.

---

## Phase 5: User Story 3 — Cross-capability data reach caught (Priority: P1)

**Goal**: No project outside the `Tenancy.*` family can reference `Tenancy.Infrastructure` or its
persistence types, and the one-capability fact is pinned.

**Independent Test**: Add a project under `src/` outside `Tenancy.*` referencing
`Tenancy.Infrastructure`, run the suite, confirm it fails naming the project, revert.

- [ ] T025 [US3] Extend `tests/ArchitectureTests/CapabilityBoundaryGates.cs` with the FR-008 gate: assert no `src/` project outside the `Tenancy.*` family references `Tenancy.Infrastructure` or names `TenancyDbContext`, generalising the migrated `OnlyTenancyApi_ReferencesInfrastructureDirectly` beyond today's single capability
- [ ] T026 [US3] Strengthen the migrated `NoCapabilityOtherThanTenancyExistsUnderSrc` into FR-009's pin with a failure message that tells the reader to extend the cross-capability reference gate rather than relax this expectation — describe the gate by what it checks, do not cite its requirement number (FR-008, FR-009) — the migrated test calls itself "a documented snapshot, not an enforced rule"
- [ ] T027 [US3] Prove T025 and T026 red per FR-023 by adding a throwaway second capability under `src/` that references `Tenancy.Infrastructure`, confirming both fail, reverting, and recording the demonstrations

**Checkpoint**: Adding a second capability is now a visible, gated decision.

---

## Phase 6: User Story 4 — Background jobs cannot reach tenant data (Priority: P2)

**Goal**: A background job cannot take `TenancyDbContext` or a persistence port in its
constructor, and the author is told what to do instead.

**Independent Test**: Add a `BackgroundService` under `src/` taking `TenancyDbContext`, run the
suite, confirm it fails naming the type and dependency, revert.

**Note**: FR-027's runtime backstop is already done (`3aebea6`). This phase adds the structural
gate, whose limits are stated in FR-012 — it closes the direct constructor route only.

- [ ] T028 [US4] Implement `Support/PersistencePort.cs` resolving FR-012's "persistence port" set mechanically — ports whose implementing type lives in a persistence namespace — and assert `ITenantContext` is excluded. Resolves CHK028, which found the namespace was inferred rather than named
- [ ] T029 [US4] Implement the FR-012 gate in `tests/ArchitectureTests/BackgroundJobGates.cs`: find `IHostedService` implementors and `BackgroundService` subclasses under `src/`, assert no constructor parameter is `TenancyDbContext` or a persistence port, failing with type and offending dependency named
- [ ] T030 [US4] Write the FR-012 failure message to state what to do instead and cite ADR-013, per the spec's explicit requirement — and resolve CHK027 by checking whether ADR-013 actually answers a job author; if it does not, say so in the message rather than citing it hollowly
- [ ] T031 [US4] Implement FR-013's pin asserting no such type exists under `src/`, and confirm it does not collide with T032's proof fixture — the spec resolved CHK029 by scoping all gates to `src/`
- [ ] T032 [US4] Prove T029 and T031 red per FR-023 by adding a throwaway `BackgroundService` under `src/` taking `TenancyDbContext`, confirming both fail, reverting, and recording that FR-012's proof is necessarily a reverted fixture (CHK005) since no permanent positive case exists

**Checkpoint**: The obvious background-job mistake is refused at the cheapest point, with FR-027
catching the routes no structural gate can see.

---

## Phase 7: User Story 5 — No provider SDK, no hardcoded model name (Priority: P2)

**Goal**: The pinned dependency set makes any new package a deliberate act, and no model
identifier appears in production code.

**Independent Test**: Add a provider-SDK package reference anywhere, run the suite, confirm the
pin fails naming the package, revert.

- [ ] T033 [US5] Implement the pinned dependency set in `tests/ArchitectureTests/DependencyPinGates.cs`: assert the complete package list in `Directory.Packages.props` matches a checked-in pin, seeded with today's thirteen entries. This one gate implements FR-014, FR-017, and FR-018 together
- [ ] T034 [US5] Record the pin's location and its update path in `DependencyPinGates.cs` remarks — resolving CHK015 (where the pin lives) and CHK017 (how a legitimate addition is approved, so the first one invites updating the pin rather than deleting the gate)
- [ ] T035 [US5] Decide and document the pin's scope — whole solution or `src/` only — resolving CHK016, which noted that "the solution's complete package set" means a test-only helper trips a gate whose stated purpose is forbidding validation libraries and mediators
- [ ] T036 [US5] Implement the FR-015 gate in `tests/ArchitectureTests/ModelNamingGates.cs` scanning `src/**/*.cs` for the six clarified prefixes (`gpt-`, `claude-`, `gemini-`, `llama-`, `text-embedding-`, `o1-`), with docs, specs, and tests out of scope
- [ ] T037 [US5] Implement FR-016's pin and split its two bundled facts so a failure identifies which one changed — resolving CHK018, which asked which half fails when S13 creates the capability before referencing an SDK
- [ ] T038 [US5] Prove T033, T036, and T037 red per FR-023: add `FluentValidation`, then `MediatR`, then a provider-SDK package, then a model identifier string; confirm each fails naming the offender; revert each; record all

**Checkpoint**: ADR-008, ADR-009, and ADR-021's rulings 1 and 2 are enforced by one pin plus one
source scan.

---

## Phase 8: User Story 6 — Requirement coverage cannot rot (Priority: P3)

**Goal**: Every spec-001 functional requirement has a declaring test, and losing one fails the
build.

**Independent Test**: Remove the coverage declaration from the only test covering one spec-001
requirement, run the suite, confirm it fails naming that requirement, restore.

- [ ] T039 [US6] Create `tests/ArchitectureTests/Support/CoversRequirementAttribute.cs` — a purpose-built attribute rather than `[Trait]`, so a typo is a failure rather than silent non-coverage. Its remarks should say *why* a bare trait string was rejected (no schema, key spelling unenforced), not cite the research section that decided it (research.md R3, CHK013)
- [ ] T040 [US6] Apply `[CoversRequirement("FR-0NN")]` across the existing unit and integration suites using `specs/001-auth-tenant-management/coverage.md`'s matrix as the source of truth, covering all 26 of spec 001's functional requirements
- [ ] T041 [US6] (SC-003) Implement the FR-020 and FR-021 gates in `tests/ArchitectureTests/RequirementCoverageGates.cs`: enumerate declarations by reflection over both test assemblies, assert every one of spec 001's twenty-six functional requirements (`001-FR-001` through `001-FR-026`) has at least one, and fail naming the specific requirement
- [ ] T042 [US6] Implement the FR-022 gate asserting no declaration names an identifier absent from spec 001, parsing the valid set from `specs/001-auth-tenant-management/spec.md` rather than hardcoding it
- [ ] T043 [US6] State the gate's limits in `RequirementCoverageGates.cs` remarks in its own words — it detects loss of declared coverage, not whether a declaring test meaningfully exercises the requirement it names — and record whether this slice's own requirements are in scope (FR-020, CHK010–CHK012)
- [ ] T044 [US6] Prove T041 and T042 red per FR-023 by removing one declaration and then adding a bogus identifier, confirming each failure names the requirement, restoring both, and recording the demonstrations

**Checkpoint**: T089's hand audit is protected from rotting, with its limits stated rather than
overclaimed.

---

## Phase 9: Requirements with no owning user story

**Purpose**: FR-019, FR-026, and FR-027 — added by ADR-021 acceptance and the checklist review
after the stories were written. No `[Story]` label, per the note at the top of this file.

- [ ] T045 Add central `DomainException` → `400` and `ConflictException` → `409` mapping to `src/Tenancy/Tenancy.Api/ErrorHandling/ProblemDetailsHandler.cs`, which currently sets `Status500InternalServerError` unconditionally (FR-019)
- [ ] T046 Write the FR-019 proof: a unit test asserting the handler's mapping, plus an integration test proving an unhandled `DomainException` yields `400` not `500`. Both **must be seen to fail against today's blanket-500 behaviour before T045 lands** — FR-023 requires this proof take that form since FR-019 is a behavioural guarantee, not a structural gate
- [ ] T047 (FR-019, SC-004) Confirm every existing endpoint `catch (DomainException)` block still produces its own more specific message after T045, by re-running the full suite and comparing pass counts rather than assuming additivity
- [ ] T048 Implement the FR-026 gate in `tests/ArchitectureTests/TenantIsolationGates.cs`: fail when `IgnoreQueryFilters()` appears with no arguments under `src/`, permitting the named form. Seed its remarks with the four currently-compliant call sites
- [ ] T049 Prove T048 red per FR-023 by changing one named call to the bare form, confirming failure names file and member, reverting, and recording it
- [x] T050 FR-027's runtime fail-closed guard for inserts with no tenant context — **done in commit `3aebea6`**, with `tests/Tenancy.IntegrationTests/Scenarios/UnsetTenantContextWriteTests.cs` written red-first (1 failed / 84 passed before the guard)

**Checkpoint**: All seventeen gates exist and all have been demonstrated red.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T051 [P] (SC-006) Assert failure-message content for every gate, so FR-024 is verified rather than eyeballed — resolving CHK006, which found the requirement satisfiable by a human glance at output
- [ ] T052 [P] Measure the full suite's runtime three times and record min/median/max in `specs/002-architecture-tests/coverage.md` against SC-005's five-minute bar, naming the hardware — resolving CHK020, which found a wall-clock bound with no stated reference environment is not reproducible
- [ ] T053 Update `docs/traceability.md`'s U12 table: mark the raw-SQL/background-job row and the provider-SDK row as addressed by this slice, and record that FR-012 closes the direct route while FR-027 closes the property. Resolves CHK041, which found no task owned this edit
- [ ] T054 [P] Correct U12's framing in the same edit — its "most plausible route to a cross-tenant leak" overstates the background-job gap against this implementation, where reads and update/delete already fail closed and only insert did not
- [ ] T055 [P] Tick S3's *Done when* checklist in `roadmap.md` and set its status to done, following the pattern used for S2
- [ ] T056 Review the 28 checklist items still open in `specs/002-architecture-tests/checklists/`, mark each resolved with a note or state why it stays open, so the checklists end the slice as a record rather than a to-do list
- [ ] T057 Add `[CoversRequirement]` declarations to this slice's own gate tests if T043 decided spec 002's requirements are in scope; skip with a recorded reason if not

---

## Dependencies & Execution Order

**Phase order**: Phase 1 → Phase 2 → Phases 3–9 (see below) → Phase 10.

**Hard sequencing** (the only ordering that is not a preference):

| Must happen first | Then | Why |
|---|---|---|
| T011 (race test green on current behaviour) | T012, T013 | Refactoring untested code and calling the result verified is the failure this ordering exists to prevent |
| T012, T013 (EF Core inversion) | T016 (FR-005 gate) | The gate is red until the violation is cleared |
| T005–T008 (helpers + migration) | Every gate task | All gates use the shared helpers |
| T010 (where proofs are recorded) | Every proof task | Otherwise each proof picks its own artifact |
| T046 (FR-019 proof red) | T045 (central mapping) | FR-023 requires the behavioural proof be seen failing first |
| T039 (attribute) | T040, T041, T042 | Nothing to reflect over until it exists |

**Story independence**: US2, US3, US4, US5, US6 and Phase 9 are mutually independent once Phase 2
lands. US1 is independent too, but carries the only production refactor, so doing it first keeps
the tree green for everything else.

**Parallel opportunities**:

- T006, T007 in parallel (different files, no shared state)
- After Phase 2: Phases 4, 5, 6, 7, 8 and Phase 9's T048/T049 can proceed concurrently — each gate
  is its own file
- T051, T052, T054, T055 in parallel within Phase 10
- **Not parallel**: any two proof tasks. Each mutates the working tree and reverts, so two at once
  will corrupt each other's baseline

---

## Implementation Strategy

**MVP is Phase 1 + Phase 2 + Phase 3 (US1).** That delivers the gate with a live violation to
clear, which is the only part of this slice that changes production behaviour and the only part
that has already demonstrated it catches something S2's review missed.

**Then, in value order**: US2 (raw SQL — U12 calls it the serious one) → US3 (cross-capability) →
Phase 9's FR-019/FR-026 → US4 → US5 → US6.

**Incremental delivery**: each phase ends green and independently useful. A gate landed without its
proof task is not done — FR-023 makes the proof part of the definition, and the `testing` skill's
red flag list names "an architecture test nobody has verified can actually fail" explicitly.

---

## Task Summary

| Phase | Story | Tasks | Count |
|---|---|---|---|
| 1 Setup | — | T001–T004 | 4 (done) |
| 2 Foundational | — | T005–T010 | 6 (done) |
| 3 | US1 (P1) 🎯 MVP | T011–T018 | 8 |
| 4 | US2 (P1) | T019–T024 | 6 |
| 5 | US3 (P1) | T025–T027 | 3 |
| 6 | US4 (P2) | T028–T032 | 5 |
| 7 | US5 (P2) | T033–T038 | 6 |
| 8 | US6 (P3) | T039–T044 | 6 |
| 9 Unowned | — | T045–T050 | 6 (1 done) |
| 10 Polish | — | T051–T057 | 7 |
| **Total** | | | **57** (10 done, 47 open) |

**Checklist items resolved by tasks**: 17 of the 28 still open are assigned to a specific task —
CHK001 (T010), CHK005 (T032), CHK006 (T051), CHK010/011 (T043), CHK012 (T043), CHK013 (T039),
CHK015 (T034), CHK016 (T035), CHK017 (T034), CHK018 (T037), CHK019 (T009), CHK020 (T052),
CHK027 (T030), CHK028 (T028), CHK033 (T020), CHK034 (T022), CHK036 (T019), CHK041 (T053).
T056 sweeps the remainder so none is silently dropped.

**Success-criteria coverage** (added after analyze finding G1, which found four of six were
covered in substance but cited by no task): SC-001 → T010 plus every proof task (T017, T023, T027,
T032, T038, T044, T046, T049); SC-002 → T013, T015, T016; SC-003 → T041, T042; SC-004 → T018,
T047; SC-005 → T052; SC-006 → T051.

**Coverage check**: all 27 functional requirements map to at least one task — FR-001/003 (T001,
T004), FR-002 (T008, T009), FR-004/005 (T015–T017), FR-006/007 (T011–T014), FR-008/009
(T025–T027), FR-010/011 (T019–T024, FR-011's relocation proof in T023), FR-012/013 (T028–T032), FR-014/016/017/018 (T033–T038),
FR-015 (T036), FR-019 (T045–T047), FR-020/021/022 (T039–T044), FR-023 (every proof task),
FR-024 (T051), FR-025 (T052), FR-026 (T048, T049), FR-027 (T050, done).
