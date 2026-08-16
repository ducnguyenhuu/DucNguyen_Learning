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

- [ ] CHK001 Does FR-023 say **where** the required demonstration is recorded? It states the
      demonstration "MUST be recorded" but names no artifact — commit message, a doc, a test
      comment, and `quickstart.md`'s table are all plausible and mutually exclusive. An
      unrecorded-where obligation cannot be audited. [Gap, Measurability, Spec §FR-023]
- [x] CHK002 **Does FR-023's eleven-gate list conflict with `quickstart.md`?** FR-023 enumerates
      FR-004, 005, 008, 010, 012, 014, 015, 017, 018, 019, 020 — deliberately excluding the three
      absence pins. But `quickstart.md` line 71 states the pins get "the same exercise in
      reverse". One document requires eight proofs the other does not. [Conflict, Spec §FR-023 vs
      quickstart §2] — **Resolved 2026-08-15**: `quickstart.md` was right. FR-023's rationale applies to
      a pin unchanged — a pin that would not notice the thing appearing is decoration — so the three
      pins are now in the list. **Eleven became sixteen**, and quickstart was updated to match.
- [ ] CHK003 Is "before being **accepted**" defined? FR-023 conditions acceptance on the
      demonstration, but no requirement says who accepts, or what artifact records acceptance.
      [Ambiguity, Spec §FR-023]
- [ ] CHK004 Does any requirement say a gate must be **re-proven when it changes**? SC-001 says
      "demonstrated once per gate". A gate refactored in S4 could silently lose its ability to
      fail, and nothing in the spec would catch that. [Gap, Coverage, Spec §SC-001]
- [ ] CHK005 For FR-012, whose proof `quickstart.md` says is "a temporary fixture that gets
      reverted" — does any requirement state that a **reverted** proof satisfies FR-023? After the
      revert, no artifact in the repository demonstrates the gate works. [Gap, Measurability,
      Spec §FR-012, §FR-023]
- [ ] CHK006 Is FR-024's requirement testable as written? It says failures "MUST name the specific
      offending project, package, call site, type, or requirement", but does not say this is
      asserted — leaving it satisfiable by a human glance at output. [Measurability, Spec §FR-024]

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
- [ ] CHK012 Does FR-020's scope cover spec **002's own** requirements, or only spec 001's? Its
      wording says spec 001 only. If S3's gates need no coverage declarations, is that a decision
      or an oversight? [Gap, Coverage, Spec §FR-020]
- [ ] CHK013 Is the coverage declaration's **storage location** specified? FR-020 says
      "machine-readable form attached to the test itself"; `research.md` R3 chooses a custom
      attribute. Does the requirement constrain it enough that a different choice would be
      non-compliant, or is R3 free to change? [Clarity, Traceability, Spec §FR-020, research §R3]
- [ ] CHK014 Does any requirement address spec 001's **success criteria** (SC-001–SC-009), or only
      its functional requirements? Roadmap S3's *Done when* says "every FR", so SCs may be
      deliberately out of scope — is that stated? [Coverage, Assumption]

## The pinned dependency set — is the clarified mechanism fully specified?

- [ ] CHK015 **Where is the pin recorded?** The Key Entities entry defines the pinned dependency
      set conceptually but names no location — a test constant, a checked-in file, or
      `Directory.Packages.props` itself all differ in how a reviewer sees a change to it.
      [Gap, Measurability, Spec §Key Entities, Clarifications 2026-08-15]
- [ ] CHK016 Is the pin's **scope** stated — whole solution, or `src/` only? The clarification says
      "the solution's complete package set", which means adding a test-only helper package trips a
      gate whose stated purpose is forbidding validation libraries and mediators. Is that intended
      or incidental? [Ambiguity, Spec §FR-014, Clarifications]
- [ ] CHK017 Does any requirement state how a **legitimate** package addition is approved? The pin
      is deliberately noisy by design; without a stated update path, the first legitimate addition
      invites deleting the gate rather than updating the pin. [Gap, Spec §Key Entities]
- [ ] CHK018 Does FR-016 bundle two independent facts into one requirement — "no provider SDK is
      referenced" *and* "no AI Platform capability exists"? When S13 creates the capability but not
      yet an SDK reference, which half fails, and is that the intended signal? [Clarity, Spec
      §FR-016]

## Migration and suite-level requirements

- [ ] CHK019 How is FR-002's "no loss of coverage" **verified**? It requires each assertion made
      today to still be made after migration, but names no mechanism — a diff review, an assertion
      count, or a passing-test count are materially different bars. [Measurability, Spec §FR-002]
- [ ] CHK020 Is FR-025's five-minute bound tied to a **reference environment**? S2's baseline was
      measured on macOS arm64; CI hardware does not exist yet. A wall-clock bound without stated
      hardware is not reproducible. [Measurability, Spec §FR-025, §SC-005]
- [ ] CHK021 Does FR-003's exclusion of `ContractTests/`/`EndToEndTests/` create an obligation on
      S9/S7, or merely record a non-decision here? A deferral with no receiving slice named in the
      *other* slice's spec tends to be forgotten. [Traceability, Spec §FR-003]
- [ ] CHK022 Is SC-006 measurable? "A developer... learns the exact offending location from the
      failure output alone, without asking another person" describes a human outcome with no
      stated evidence — is it satisfied by FR-024's assertions, and if so should SC-006 point at
      them? [Measurability, Spec §SC-006, §FR-024]

## Notes

- Check items off as reviewed: `[x]`, appending `— **Resolved <date>**: <what changed>` as
  `001/checklists/security.md` does.
- CHK001–CHK022 belong to this file. [tenant-isolation.md](tenant-isolation.md) continues at
  CHK023 so a bare "CHK0NN" is unambiguous across both checklists for this feature.
- Items marked `[Conflict]` (CHK002, CHK007) are the two that need a decision rather than a
  wording fix, and should be resolved before `/speckit.tasks` — a task list generated from a
  spec that disagrees with `quickstart.md` about how many gates need proofs will be wrong in
  either direction.
