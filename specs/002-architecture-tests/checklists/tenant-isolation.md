# Tenant-Isolation Gate Requirements Quality Checklist: Architecture Tests

**Purpose**: Interrogate whether FR-010–FR-013 — the two gates that stand between this platform
and a cross-tenant leak — are specified precisely enough to be built and trusted. A review of the
English, not the code.
**Created**: 2026-08-15
**Feature**: [spec.md](../spec.md) · [research.md](../research.md) · [ADR-013](../../../docs/adr/ADR-013-multi-tenancy-model.md) · [U12](../../../docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs)
**Depth**: Standard (reviewer-grade, 20 items)
**Scope**: FR-010, FR-011 (raw SQL), FR-012, FR-013 (background jobs)
**Numbering**: continues from [gate-efficacy.md](gate-efficacy.md), which holds CHK001–CHK022

**Why these four requirements get their own checklist**: `docs/traceability.md` U12 calls the
raw-SQL / background-job gap *"the serious one"* and *"the most plausible route to a cross-tenant
leak"*, and Constitution Principle IV calls an isolation failure existential. Following S2's
`security.md` reasoning: a vague gate-efficacy requirement costs a rework; a vague isolation
requirement costs the company.

**How to use**: answer each item with the spec text in front of you. Point at the sentence, or
mark the item failed.

---

## Does FR-012 actually close the gap U12 describes?

- [x] CHK023 **U12's stated danger is "a background job running without tenant context". FR-012
      forbids a job from *taking a persistence dependency*. Are those the same property?** A job
      that takes only `ITenantContext` (explicitly permitted), never sets it, and calls an
      Application use case such as `ListMembers` passes FR-012's gate and still queries with
      unset tenant context. [Coverage, Gap, Spec §FR-012 vs U12] — **Resolved 2026-08-15**: no, they are not the same
      property. FR-012 now records that limit explicitly, and **FR-027** closes the property at
      runtime instead: inserting an `ITenantOwned` entity with unset context throws. Verified
      red-first (1 failed / 84 passed before the guard).
- [x] CHK024 Does FR-012 cover a job that obtains data access **without a constructor parameter**
      — resolving `TenancyDbContext` from `IServiceProvider`, or from a static/ambient accessor?
      Constructor inspection is blind to service-locator style, and no requirement forbids it.
      [Gap, Coverage, Spec §FR-012] — **Resolved 2026-08-15**: confirmed **unclosable** by a structural gate — a
      `BackgroundService` is a singleton and *must* use `IServiceScopeFactory` to reach scoped
      services, so forbidding that pattern would forbid the correct one. Closed by FR-027 at
      runtime instead.
- [x] CHK025 Does FR-012 cover a job that depends on an **Application use case** rather than a
      persistence port? Use cases are not persistence ports under the clarified mechanical
      definition, so `ListMembers`, `RemoveMember`, and `ChangeMemberRole` are all permitted
      dependencies today. [Gap, Coverage, Spec §FR-012, Clarifications 2026-08-15] — **Resolved 2026-08-15**: correct,
      use cases remain permitted dependencies. Not closed structurally (that would forbid a job
      doing anything useful); closed by FR-027, which fires wherever the write originates.
- [x] CHK026 Is there any **runtime** requirement backing the structural gate — that a
      tenant-scoped operation with no tenant context fails loudly rather than silently? The spec
      specified only a compile/test-time gate, so a job that evades it had no second line of
      defence. [Gap, Coverage, Principle IV] — **Resolved 2026-08-15**: **FR-027 added.** This item as originally
      written said "returning an empty or **wrong-tenant** result" — the second half was wrong and
      is corrected here: `CurrentTenantId` is a non-nullable struct, so unset means `Guid.Empty`,
      against which reads match no row and update/delete already throw. Only *insert* failed open,
      producing an orphan rather than a leak. The verified behaviour is now recorded on FR-027.
- [ ] CHK027 Does the spec state what a background job **should** do, now that the clarification
      removed the sanctioned abstraction? FR-012 requires the failure message to "state what to do
      instead and cite ADR-013", but ADR-013 predates this question and describes request-scoped
      resolution. Does it actually answer a job author? [Traceability, Clarity, Spec §FR-012]
- [ ] CHK028 Is the mechanical definition of **"persistence port"** unambiguous? "A port whose
      implementing type lives in a persistence namespace" — is the namespace named, or inferred?
      `Tenancy.Infrastructure.Persistence` and `Tenancy.Infrastructure.Persistence.Audited` both
      exist, and a future capability may not use the word "Persistence" at all. [Clarity,
      Ambiguity, Spec §FR-012]
- [x] CHK029 Does FR-013's absence pin scope itself to `src/`, or does it include `tests/`? FR-023's
      proof for FR-012 requires temporarily adding a background job — if the pin scans `tests/`,
      the proof fixture trips the pin, and the two requirements interfere. [Conflict, Spec §FR-012,
      §FR-013, §FR-023] — **Resolved 2026-08-15**: resolved by one rule stated once for all gates: **they scan
      `src/`, not `tests/`**, and proofs add the violation to `src/` temporarily then revert.
- [ ] CHK030 Is `IMembershipDirectory`'s inclusion deliberate and stated? It is the codebase's one
      sanctioned cross-tenant reader, so forbidding it to jobs is defensible — but a job iterating
      tenants is exactly the case it was built for. Is the tension recorded? [Assumption, Spec
      §FR-012]

## Raw SQL — is the forbidden set enumerable?

- [ ] CHK031 **FR-010 ends with "or equivalent" — the same open-endedness the clarification session
      removed from FR-014/FR-017/FR-018, left unresolved here.** Does "equivalent" include
      `Database.ExecuteSql`, `SqlCommand` used directly, a future Dapper dependency, or a stored
      procedure call? The package pin does not cover SQL constructs. [Ambiguity, Spec §FR-010 vs
      Clarifications]
- [x] CHK032 Does FR-010 state its **scan scope**? `research.md` R4 scopes it to `.cs` files under
      `src/`, but the requirement says only "at a call site". A test that sets up data with raw SQL
      would be a violation under the requirement and permitted under the research decision.
      [Gap, Conflict, Spec §FR-010 vs research §R4] — **Resolved 2026-08-15**: FR-010 now states `src/` in its own
      text, with the reason tests are excluded.
- [ ] CHK033 Is **"member"** in FR-011 defined precisely enough to key an allow-list? Two overloads
      of the same method name, a local function, and a lambda inside a method are all plausibly
      "the member", and they are not interchangeable for the stated purpose of catching relocation.
      [Clarity, Measurability, Spec §FR-011]
- [ ] CHK034 Does any requirement demand a **justification** alongside a new allow-list entry?
      Adding an entry is a one-line diff. FR-011 makes relocation visible but nothing requires the
      author to state why the new raw SQL is safe — which is the whole point of the word "audited".
      [Gap, Spec §FR-011, §Key Entities]
- [ ] CHK035 Does anything require the **existing** audited call to remain correct? The gate checks
      that the call is allow-listed, not that its tenant scoping is still sound. A future edit
      inside `RemoveMembershipAsync` keeps the allow-list entry valid while changing its safety.
      [Coverage, Gap, Spec §FR-010, §FR-011]
- [ ] CHK036 Is the allow-list's **location and format** specified? FR-011 fixes the key (file plus
      member) but not where the list lives, so a reviewer cannot tell whether a change to it is
      visible in a diff they would notice. [Gap, Measurability, Spec §FR-011]
- [ ] CHK037 Does FR-010 address raw SQL reaching the database through **EF Core interceptors or
      migrations**? `TenantSaveChangesInterceptor` exists and migrations contain generated SQL by
      construction — are these out of scope by intent, and is that stated? [Coverage, Assumption,
      Spec §FR-010]

## Consistency with the isolation model these gates serve

- [ ] CHK038 Do FR-010 and FR-012 reference the mechanism they protect? Both exist because ADR-013
      relies on a global query filter plus ambient `CurrentTenantId`. Neither requirement names
      that dependency, so a future reader cannot tell what breaks if the gate is removed.
      [Traceability, Spec §FR-010, §FR-012]
- [ ] CHK039 Spec 001 §FR-008 requires preventing **all** cross-tenant data access and §SC-004
      permits zero exceptions. Do FR-010/FR-012 claim to complete that, or only to close two named
      routes? The spec should not let a reader infer the stronger claim. [Clarity, Traceability,
      Spec §FR-010, §FR-012 vs spec-001 §FR-008]
- [x] CHK040 Is there a requirement covering the **third** route U12 does not name — a cross-tenant
      read through `IgnoreQueryFilters`? **Four such call sites are live today**
      (`InvitationRepository.cs:57`, `MembershipRepository.cs:82` and `:105`,
      `MembershipDirectory.cs:40`), all correctly passing the named `"TenantFilter"` after T095's
      audit. The spec mentions `IgnoreQueryFilters` **zero times**, so nothing stops a fifth call
      site from using the bare no-arg form that T095 existed to remove — a construct that disables
      every filter, not just tenancy. This is the same shape as FR-010's raw-SQL gate and has more
      existing instances than raw SQL does. [Gap, Coverage, research-001 §R3] — **Resolved 2026-08-15**: **FR-026
      added** — the bare no-arg form is forbidden under `src/`, the named form stays permitted. No
      allow-list needed since all four live sites already comply.
- [ ] CHK041 Does the spec say whether these two gates are considered sufficient to mark U12's
      first row **closed**, or only partially addressed? `docs/traceability.md` will need updating
      either way, and no requirement or task owns that edit. [Gap, Traceability, U12]
- [x] CHK042 Are FR-012's acceptance scenarios internally consistent after the clarification?
      Scenario 2a permits a job whose constructor takes only `ITenantContext`, while CHK023 above
      suggests that exact shape can still leak. If both are correct, the scenario is proving
      something narrower than the story claims. [Conflict, Spec §US4 scenarios] — **Resolved 2026-08-15**: scenario 2a
      now says outright that passing FR-012 does not make the job safe, and points at FR-027 as
      what refuses the write.

## Notes

- Check items off as reviewed: `[x]`, appending `— **Resolved <date>**: <what changed>`.
- **CHK023, CHK024, CHK025, CHK040 are the substantive ones**, and CHK040 is arguably a
  missing requirement rather than a wording gap: four live call sites, zero spec coverage. They share a shape: FR-012 and
  FR-010 gate the *routes that exist today* rather than the *property* U12 cares about, so a
  determined or merely unlucky author can satisfy every gate and still leak. Whether that is
  acceptable for this slice is a decision, not a wording fix.
- CHK029, CHK032, CHK042 are conflicts between documents that should be settled before
  `/speckit.tasks`, since a task list will otherwise encode one side arbitrarily.
