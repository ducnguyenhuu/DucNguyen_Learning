# Gate Efficacy Requirements Quality Checklist: Architecture Tests

**Purpose**: Interrogate whether the *requirements about the gates themselves* are complete,
unambiguous, and measurable — before any gate is written. This is a review of the English, not
of the code.
**Created**: 2026-08-15
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [research.md](../research.md) · [quickstart.md](../quickstart.md)
**Depth**: Standard (reviewer-grade, 22 items)
**Scope**: FR-001–FR-003 (test project), FR-009/FR-013/FR-016 (absence pins), FR-020–FR-025 (coverage and gate quality), SC-001, SC-005, SC-006

**Why this checklist exists separately from [requirements.md](requirements.md)**: that one checks
generic spec quality and has passed three iterations plus a clarification session. This one
interrogates the single failure mode that would make this entire slice worthless — a gate that
reports green while the boundary is broken. Every other slice ships a capability; this one ships
only gates, so the requirements *about* gates carry the whole value.

**How to use**: answer each item with the spec text in front of you. An item is satisfied only if
you can point at the sentence that satisfies it. "That's obviously implied" is a failure.

---

## Proof-of-failure — is the FR-023 obligation actually specifiable?

- [x] CHK001 Does FR-023 say **where** the required demonstration is recorded? It states the
      demonstration "MUST be recorded" but names no artifact — commit message, a doc, a test
      comment, and `quickstart.md`'s table are all plausible and mutually exclusive. An
      unrecorded-where obligation cannot be audited. [Gap, Measurability, Spec §FR-023] — **Resolved
      2026-08-17 (T010)**: a `Demonstrated` column was added to both gate tables in
      `quickstart.md` §2, seeded `_pending_` and filled by each proof task with
      `<commit-hash> (YYYY-MM-DD)`. Chosen over a separate `proofs.md` because there is no PR to
      attach output to in this repo and it keeps a gate's violation/expected-outcome/proof-location
      facts in one row. All 17 rows are now filled (per the proof tasks through T032/T038/T044/T046/T049).
- [x] CHK002 **Does FR-023's eleven-gate list conflict with `quickstart.md`?** FR-023 enumerates
      FR-004, 005, 008, 010, 012, 014, 015, 017, 018, 019, 020 — deliberately excluding the three
      absence pins. But `quickstart.md` line 71 states the pins get "the same exercise in
      reverse". One document requires eight proofs the other does not. [Conflict, Spec §FR-023 vs
      quickstart §2] — **Resolved 2026-08-15**: `quickstart.md` was right. FR-023's rationale applies to
      a pin unchanged — a pin that would not notice the thing appearing is decoration — so the three
      pins are now in the list. **Eleven became sixteen**, and quickstart was updated to match.
- [ ] CHK003 Is "before being **accepted**" defined? FR-023 conditions acceptance on the
      demonstration, but no requirement says who accepts, or what artifact records acceptance.
      [Ambiguity, Spec §FR-023] — **Left open 2026-08-17**: T010 answered *where* the demonstration is
      recorded (the `Demonstrated` column), but nothing in the spec or `quickstart.md` says *who*
      accepts a gate or what artifact records that act of acceptance (a reviewer sign-off, a PR
      approval — none of which this repo currently has a mechanism for). Genuinely still open; no
      later task in this slice addresses it. Deferred as an acknowledged gap, not tracked against
      any later slice.
- [ ] CHK004 Does any requirement say a gate must be **re-proven when it changes**? SC-001 says
      "demonstrated once per gate". A gate refactored in S4 could silently lose its ability to
      fail, and nothing in the spec would catch that. [Gap, Coverage, Spec §SC-001] — **Left open
      2026-08-17**: confirmed still true of the spec as it stands at the end of this slice — SC-001
      and FR-023 both describe a one-time demonstration with no re-proof-on-change obligation. No
      task in Phases 1-10 added one. Left open deliberately: re-proving gates on every change to
      the gate file itself is a process/tooling question (e.g. mutation testing on the
      `tests/ArchitectureTests` project) better suited to a later slice's CI work (S7) than to a
      wording fix here.
- [x] CHK005 For FR-012, whose proof `quickstart.md` says is "a temporary fixture that gets
      reverted" — does any requirement state that a **reverted** proof satisfies FR-023? After the
      revert, no artifact in the repository demonstrates the gate works. [Gap, Measurability,
      Spec §FR-012, §FR-023] — **Resolved 2026-08-17 (T032)**: T032 executed and recorded exactly this —
      added a throwaway `ScratchBackgroundJob` under `src/`, captured the verbatim red failure output
      for both `BackgroundJobGates` facts, reverted the fixture, and confirmed `quickstart.md`
      already states explicitly (added during the spec's own clarification pass) that "FR-012 has
      no positive case while no background job exists. Its proof is therefore a temporary fixture
      that gets reverted, not a permanent test." The `Demonstrated` cell records the proving commit
      (`c19a97b`), which is the artifact FR-023 requires — the reverted state itself is expected,
      not a gap.
- [x] CHK006 Is FR-024's requirement testable as written? It says failures "MUST name the specific
      offending project, package, call site, type, or requirement", but does not say this is
      asserted — leaving it satisfiable by a human glance at output. [Measurability, Spec §FR-024]
      — **Resolved 2026-08-17 (T051)**: a structured audit of every fact across all eight gate
      files (`tests/ArchitectureTests/FAILURE_MESSAGE_AUDIT.md`) confirms which facts hand-compose
      the offender into their message text (most do) versus relying on the assertion framework's
      own diff output (`CapabilityBoundaryGates.cs`'s 7 facts, and the general pin check in
      `DependencyPinGates.cs`). New lightweight tests (`FailureMessageContentTests.cs`) assert the
      offender-capturing regexes directly, and the one previously-deferred red path
      (`PinnedPackageNames_ContainNoKnownProviderSdkNamePattern`) was proven red and reverted. The
      framework-diff-only facts are flagged as a real, if minor, gap against FR-024's letter — not
      fixed, as disproportionate scope for this polish task — so this is resolved with a stated,
      honest residual limitation rather than a claim of perfect compliance.

## "The build MUST fail" — does the spec mean what it says?

- [x] CHK007 **Nine requirements say "the build MUST fail", but there is no build to fail.**
      `plan.md` states CI is S7 and that in this slice the phrase means "fails `dotnet test`" run
      by hand. No requirement carries that qualification, so as written the spec asserts an
      enforcement mechanism that does not exist until four slices later. [Conflict, Spec §FR-004,
      005, 008, 010, 012, 014, 015, 017, 018 vs plan §Technical Context] — **Resolved 2026-08-15**: the phrase now has
      **one definition** at the head of the Requirements section instead of nine unqualified claims,
      and the missing enforcement is a recorded deferral rather than an implication.
- [x] CHK008 Given no CI, does any requirement state what stops a developer committing without
      running the gates at all? Constitution Principle VII prefers gates over vigilance; an
      unenforced local test suite *is* vigilance. Is that gap acknowledged as a requirement
      limitation or left implicit? [Gap, Traceability, Principle VII] — **Resolved 2026-08-15**: acknowledged
      explicitly: until S7 this is vigilance, not a gate.
- [x] CHK009 Is there a requirement that these gates be wired into CI when S7 arrives? Without
      one, the S7 slice has no inherited obligation and the gates could stay local forever.
      [Gap, Coverage] — **Resolved 2026-08-15**: **Deferred Requirements table added**, using the mechanism spec 001
      used to hand `old-FR-028` to this slice — which is exactly why that one was not lost.
      `old-FR-029` → S7 (pipeline), `old-FR-030` → S8/S10 (the job abstraction).

## Requirement-coverage gate — does a declaration prove coverage?

- [x] CHK010 **Does FR-020 conflate "declares coverage" with "covers"?** It requires each spec-001
      requirement to have "at least one test that declares... that it covers that requirement".
      A test that declares `FR-007` and asserts something unrelated satisfies this literally.
      The gate is trivially gameable by attribute-spraying. [Gap, Measurability, Spec §FR-020] — **Resolved 2026-08-15**:
      confirmed and **stated in FR-020** rather than fixed — verifying substance needs human
      judgement. The gate detects *loss* of declared coverage; T089's hand audit remains the
      substantive evidence and SC-003 must not be read as claiming more.
- [x] CHK011 Is there any requirement that the declaring test be **meaningful** for the
      requirement it names — or is declaration-existence the whole contract? If the latter, is
      that limitation stated so a later reader does not overestimate SC-003? [Gap, Spec §FR-020,
      §SC-003] — **Resolved 2026-08-15**: the latter, and the limitation is now stated in FR-020 itself.
- [x] CHK012 Does FR-020's scope cover spec **002's own** requirements, or only spec 001's? Its
      wording says spec 001 only. If S3's gates need no coverage declarations, is that a decision
      or an oversight? [Gap, Coverage, Spec §FR-020] — **Resolved 2026-08-17 (T043)**: a decision,
      not an oversight. `RequirementCoverageGates.cs`'s class remarks now state explicitly "Scope:
      spec 001 only, not this slice's own requirements," with the reasoning recorded: broadening
      scope would create a bootstrapping oddity (the coverage gate's own specifying requirement,
      spec 002's FR-020, would need a declaring test before one could exist). T057 (Phase 10)
      confirmed this decision and skipped adding `[CoversRequirement]` declarations to spec 002's
      own gate tests for the stated reason.
- [x] CHK013 Is the coverage declaration's **storage location** specified? FR-020 says
      "machine-readable form attached to the test itself"; `research.md` R3 chooses a custom
      attribute. Does the requirement constrain it enough that a different choice would be
      non-compliant, or is R3 free to change? [Clarity, Traceability, Spec §FR-020, research §R3]
      — **Resolved 2026-08-17 (T039)**: `CoversRequirementAttribute` (in
      `tests/ArchitectureTests/Support/CoversRequirementAttribute.cs`) is the storage location —
      a purpose-built attribute type, not a bare `[Trait]`. Its remarks state the concrete reason a
      free-form trait was rejected (an unenforced key/value string means a typo compiles and is
      indistinguishable from no coverage claim at all), which fixes the location and format R3 only
      proposed — a different choice now would visibly diverge from the checked-in gate that reads
      this exact attribute type.
- [x] CHK014 Does any requirement address spec 001's **success criteria** (SC-001–SC-009), or only
      its functional requirements? Roadmap S3's *Done when* says "every FR", so SCs may be
      deliberately out of scope — is that stated? [Coverage, Assumption] — **Left open 2026-08-17**:
      confirmed still true — `roadmap.md`'s S3 *Done when* list (ticked complete by T055) and
      spec.md's FR-020 both talk only about spec 001's functional requirements; no requirement or
      task in this slice addresses spec 001's SC-001 through SC-009 directly. Left open as a
      documented, deliberate scope limitation rather than fixed, since retrofitting SC-level
      coverage tracking was never in this slice's scope and would be a new requirement, not a
      wording clarification.

## The pinned dependency set — is the clarified mechanism fully specified?

- [x] CHK015 **Where is the pin recorded?** The Key Entities entry defines the pinned dependency
      set conceptually but names no location — a test constant, a checked-in file, or
      `Directory.Packages.props` itself all differ in how a reviewer sees a change to it.
      [Gap, Measurability, Spec §Key Entities, Clarifications 2026-08-15] — **Resolved 2026-08-17
      (T034)**: the pin lives inline as a checked-in `PinnedPackageNames` array directly in
      `tests/ArchitectureTests/DependencyPinGates.cs`, documented in the class-level remarks
      (mirroring `RawSqlGates`' allow-list precedent) rather than a separate config file.
- [x] CHK016 Is the pin's **scope** stated — whole solution, or `src/` only? The clarification says
      "the solution's complete package set", which means adding a test-only helper package trips a
      gate whose stated purpose is forbidding validation libraries and mediators. Is that intended
      or incidental? [Ambiguity, Spec §FR-014, Clarifications] — **Resolved 2026-08-17 (T035)**:
      stated as intended, not incidental. `DependencyPinGates.cs`'s remarks record that
      `Directory.Packages.props` is solution-wide with no mechanism to scope a `PackageVersion`
      entry to `src/` only, so the pin's scope is unavoidably the whole solution — and that this is
      an accepted, intentional consequence: the gate's real job is "no accidental/undeclared
      dependency addition, full stop," of which forbidding a provider SDK is only the headline case.
- [x] CHK017 Does any requirement state how a **legitimate** package addition is approved? The pin
      is deliberately noisy by design; without a stated update path, the first legitimate addition
      invites deleting the gate rather than updating the pin. [Gap, Spec §Key Entities] —
      **Resolved 2026-08-17 (T034)**: `DependencyPinGates.cs`'s remarks and
      `CentralPackageSet_MatchesThePinnedNameList`'s own failure message both state the update path
      explicitly: update both `Directory.Packages.props` and `PinnedPackageNames` in the same PR —
      so the first person who trips this gate is told to update the pin, not delete the test.
- [x] CHK018 Does FR-016 bundle two independent facts into one requirement — "no provider SDK is
      referenced" *and* "no AI Platform capability exists"? When S13 creates the capability but not
      yet an SDK reference, which half fails, and is that the intended signal? [Clarity, Spec
      §FR-016] — **Resolved 2026-08-17 (T037)**: split into two independent `[Fact]` methods —
      `PinnedPackageNames_ContainNoKnownProviderSdkNamePattern` and
      `NoAiPlatformCapabilityDirectoryExistsUnderSrc` — so a future S13 failure identifies
      unambiguously, by test method name and message, which of the two bundled facts changed.

## Migration and suite-level requirements

- [x] CHK019 How is FR-002's "no loss of coverage" **verified**? It requires each assertion made
      today to still be made after migration, but names no mechanism — a diff review, an assertion
      count, or a passing-test count are materially different bars. [Measurability, Spec §FR-002]
      — **Resolved 2026-08-17 (T009)**: verified concretely, not eyeballed. All 5 migrated boundary
      tests and their exact assertion counts (6 total) were read directly from source, checked
      against `dotnet test` output for both `ArchitectureTests` (6 passed, up from 0) and
      `Tenancy.UnitTests` (107 passed, down from 112 — an exact offsetting 5-test move), and
      recorded in `tests/ArchitectureTests/README.md`'s "Migrated Tests: Assertion Count
      Verification" section as a durable, checked-in artifact — an assertion-count bar, not a
      passing-test-count bar alone.
- [x] CHK020 Is FR-025's five-minute bound tied to a **reference environment**? S2's baseline was
      measured on macOS arm64; CI hardware does not exist yet. A wall-clock bound without stated
      hardware is not reproducible. [Measurability, Spec §FR-025, §SC-005] — **Resolved 2026-08-17
      (T052)**: three real wall-clock runs (21.7s/22.2s/22.3s) recorded in
      `specs/002-architecture-tests/coverage.md`, explicitly naming the hardware (Apple M3 Pro, 18GB
      RAM, macOS 25.5.0 ARM64) so the bound is reproducible against a stated reference environment,
      not just S2's earlier unattributed ~21s figure.
- [ ] CHK021 Does FR-003's exclusion of `ContractTests/`/`EndToEndTests/` create an obligation on
      S9/S7, or merely record a non-decision here? A deferral with no receiving slice named in the
      *other* slice's spec tends to be forgotten. [Traceability, Spec §FR-003] — **Left open
      2026-08-17**: confirmed still true — neither `docs/traceability.md` nor `roadmap.md` mentions
      `ContractTests/` or `EndToEndTests/` anywhere (checked via direct search), so no receiving
      slice (S7/S9) currently carries an inherited obligation for this deferral. Left open rather
      than resolved: this slice correctly declines to scaffold those test layers, but the follow-up
      of recording the obligation in S7's or S9's own spec was not done by any task here and is a
      real risk of being forgotten, exactly as the item warns.
- [x] CHK022 Is SC-006 measurable? "A developer... learns the exact offending location from the
      failure output alone, without asking another person" describes a human outcome with no
      stated evidence — is it satisfied by FR-024's assertions, and if so should SC-006 point at
      them? [Measurability, Spec §SC-006, §FR-024] — **Resolved 2026-08-17 (T051, incidental)**:
      resolved in substance, not in spec wording. T051's audit and new
      `FailureMessageContentTests.cs` confirm that most gates' failure messages do hand-interpolate
      the specific offending location, which is the concrete evidence SC-006's human-outcome claim
      rests on. The spec text itself was not edited to add an explicit cross-reference from SC-006
      to FR-024 — that wording improvement is still open as a documentation nicety, but the
      measurability gap the item raised is closed by T051's audit existing as checked-in evidence.

## Notes

- Check items off as reviewed: `[x]`, appending `— **Resolved <date>**: <what changed>` as
  `001/checklists/security.md` does.
- CHK001–CHK022 belong to this file. [tenant-isolation.md](tenant-isolation.md) continues at
  CHK023 so a bare "CHK0NN" is unambiguous across both checklists for this feature.
- Items marked `[Conflict]` (CHK002, CHK007) are the two that need a decision rather than a
  wording fix, and should be resolved before `/speckit.tasks` — a task list generated from a
  spec that disagrees with `quickstart.md` about how many gates need proofs will be wrong in
  either direction.
