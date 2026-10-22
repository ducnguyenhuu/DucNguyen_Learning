# Security & Tenancy Requirements Quality Checklist: Authentication & Tenant Management

**Purpose**: Validate that the *security and tenancy requirements themselves* are complete,
unambiguous, measurable, and mutually consistent — before any of them is implemented. This is a
review of the English, not of the code.
**Created**: 2026-08-10
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [ADR-013](../../../docs/adr/ADR-013-multi-tenancy-model.md) · [ADR-017](../../../docs/adr/ADR-017-tenant-context-resolution.md)
**Depth**: Standard (reviewer-grade, 29 items)
**Scope**: FR-001..FR-004 (authentication), FR-007..FR-010 (tenant context and isolation), FR-013..FR-019 (membership, revocation, roles), FR-022, FR-025, FR-026 (disclosure, logging, secrets)

**Why this checklist exists separately from [requirements.md](requirements.md)**: that one checks
generic spec quality and has passed four iterations. This one interrogates only the requirements
whose failure Constitution Principle IV calls *existential*. A vague UX requirement costs a
rework; a vague isolation requirement costs the company.

**How to use**: answer each item with the spec text in front of you. An item is satisfied only if
you can point at the sentence that satisfies it. "We all know what that means" is a failure.

---

## Authentication & Identity — Requirement Completeness

- [x] CHK001 Does the spec state **which** Entra tenants may issue accepted tokens — one shared tenant, each customer's own tenant, or any tenant? FR-001 says *"the organisation's corporate identity provider"* without saying whose organisation. For a multi-customer SaaS these are three materially different products. [Ambiguity, Spec §FR-001, Assumption 1] — **Resolved 2026-08-10**: Assumption 1 now states one Entra tenant explicitly and cites ADR-019. See K1 below.
- [ ] CHK002 Is *"stable user identity"* defined with criteria that make it checkable — stable across what, exactly? Sessions are named; email change, display-name change, and moving between Entra tenants are not. [Clarity, Spec §FR-003]
- [ ] CHK003 Does FR-004 enumerate **all** token validation dimensions the design relies on? It names expired, malformed, and wrong-audience. Signature and issuer validation appear only in research.md R2, not in any requirement. [Completeness, Spec §FR-004]
- [ ] CHK004 Are requirements defined for a caller who authenticates successfully but holds **no membership in any tenant** — a legitimate state immediately after first sign-in? Story 1 assumes it; no FR states the expected behaviour. [Gap, Coverage]
- [ ] CHK005 Is the requirement that the platform holds **no client secret** written anywhere, or is it only an emergent property of the chosen design? It is a genuine security property worth stating rather than rediscovering. [Gap, Completeness]

## Tenant Context & Isolation — Clarity and Measurability

- [ ] CHK006 Is the term **"tenant-scoped operation"** defined in the spec? FR-018 and SC-004 both quantify over it (*"every tenant-scoped operation"*), and neither an enumeration nor a definition exists in spec.md. An unbounded "every" cannot be evidenced. [Gap, Measurability, Spec §FR-018, §SC-004]
- [ ] CHK007 Are the operations that legitimately run **without** tenant context identified as requirements, or only as a design decision? ADR-017 enumerates exactly three; spec.md implies but never states that such exceptions exist. [Traceability, Gap, Spec §FR-007]
- [x] CHK008 Is *"blending"* in FR-010 defined? As written it appears to forbid any response spanning tenants, which would prohibit the tenant-list operation Story 1 scenario 5 requires. [Conflict, Spec §FR-010 vs §US1-5] — **Resolved 2026-08-10**: FR-010 now scopes it to *"within any tenant-scoped response"* and cites ADR-017's enumerated exceptions. See K2.
- [ ] CHK009 Can FR-008's *"no response **ever** contains data belonging to a tenant the caller is not a member of"* be evidenced, given no list of responses exists in the spec? [Measurability, Spec §FR-008]
- [ ] CHK010 Does the spec state whether isolation must hold for **tenant metadata** (existence, display name, member count) as well as tenant *data*? FR-009 addresses existence; display name and aggregate counts are unaddressed. [Completeness, Spec §FR-008, §FR-009]
- [ ] CHK011 Are isolation requirements stated for surfaces **beyond the relational store** — logs, telemetry, cache keys, error messages? Principle IV names eight surfaces; spec.md's FRs address data and API only. Several of those surfaces arrive in S4, but the requirement can be written now. [Coverage, Gap, Constitution Principle IV]
- [ ] CHK012 Is the required **failure mode** on unresolvable tenant context stated as *fail closed*? FR-007 says "rejected, never defaulted", which is close — confirm it is unambiguous enough that a `Guid.Empty` sentinel could not be read as compliant. [Clarity, Spec §FR-007]

## Revocation & Membership Lifecycle — Measurability

- [ ] CHK013 Is FR-016's *"bounded, documented staleness window"* actually bounded **in the requirement**? The one-hour figure lives in Assumption 7. A requirement whose threshold is stated only in an assumption is not measurable from the requirement. [Measurability, Spec §FR-016 vs Assumption 7] ⚠️ This is the exact defect class `/speckit.analyze` found as a *coverage* gap; it is also a *wording* gap.
- [ ] CHK014 Is *"effective access"* in FR-016 defined? A removed member's existing token stays cryptographically valid; whether "effective access" means new authorization decisions or all request handling changes what compliance looks like. [Clarity, Spec §FR-016]
- [ ] CHK015 Is FR-011's invitation expiry **quantified in the requirement**, or only in Assumption 6 (7 days)? Same pattern as CHK013. [Measurability, Spec §FR-011]
- [ ] CHK016 Does FR-013 require invitation refusals to be **mutually indistinguishable**, so token validity cannot be probed? FR-009 establishes this principle for tenants; FR-013 says only "refused". The contract specifies 404 for all cases, so the requirement trails the design. [Gap, Consistency, Spec §FR-013 vs §FR-009]
- [ ] CHK017 Does FR-015's *"MUST guarantee"* explicitly extend to **concurrent** attempts? data-model.md identifies a real race in which two simultaneous removals can each observe two administrators and both succeed. The hard half of the guarantee is the unstated half. [Completeness, Spec §FR-015]
- [ ] CHK018 Are requirements defined for what happens to a **pending invitation** when its tenant is suspended, or when the inviting administrator is themselves removed? Neither state transition is addressed. [Gap, Edge Case]

## Authorization Model — Consistency

- [x] CHK019 Does the spec define an operation where the **Member** role differs from **Reader**? FR-017 mandates at least three roles, but in this slice both can read and neither can modify settings or manage membership — so the distinction is unobservable and therefore untestable. [Conflict, Measurability, Spec §FR-017, §US3-2, §US3-3] — **Resolved 2026-08-10**: Assumption 5 now records that they are identical in S2 by construction, and forbids inventing an operation to make them differ. See K3.
- [ ] CHK020 Is a **permission matrix** stated as a requirement, rather than described in prose across Story 3? *"A member can act within the tenant"* is not a specification of any permission. [Clarity, Gap, Spec §US3]
- [ ] CHK021 Does the spec state whether **listing members and pending invitations** is administrator-only? FR-014 grants it to administrators; nothing says non-administrators are excluded, and FR-019 restricts *management*, not viewing. The contract chose administrator-only. [Ambiguity, Spec §FR-014 vs §FR-019]
- [ ] CHK022 Are the **403-versus-404** semantics stated as a requirement pair, so the distinction cannot be implemented backwards? FR-018 requires 403 to be distinct from 401; FR-009 requires inaccessible to look non-existent. The interaction — member-with-wrong-role gets 403, non-member gets 404 — is inferable but never stated. [Consistency, Gap, Spec §FR-009 + §FR-018]

## Secrets, Logging & Data Minimisation

- [ ] CHK023 Is *"unnecessary personal data"* in FR-025 defined, or reducible to a decidable test? Principle XI requires minimisation to *"what the capability genuinely requires"*, which is equally undecidable as written. [Clarity, Spec §FR-025, Constitution Principle XI]
- [ ] CHK024 Does FR-026 state that a secret committed **and later removed** is still compromised, and that the remedy is rotation? The requirement forbids committing; it does not state the consequence, which is what makes the rule urgent. [Completeness, Spec §FR-026]
- [ ] CHK025 Are requirements defined for the **invitation token's** handling — that it is a credential, returned once, and never persisted in plaintext? data-model.md decides this; no FR requires it. [Gap, Traceability]

## Scenario & Edge Case Coverage

- [ ] CHK026 Is each of the 11 entries in the **Edge Cases** section traceable to a functional requirement or an explicit deferral? Several map cleanly (last administrator → FR-015); *"Database unavailable"* maps to nothing in this slice. [Traceability, Spec §Edge Cases]
- [ ] CHK027 Are **recovery** requirements defined for any security-relevant partial failure — a tenant created but its first membership not, an invitation accepted but membership write failing? Only prevention is specified. [Gap, Recovery Flow]

## Settled Decisions — written down, or merely believed?

- [ ] CHK028 For each documented deviation and deferral — SC-003 → S7, Principle VI and X partial compliance, the one-hour staleness window, Assumption 3's "same schema as Azure" — can you point at the **sentence in a versioned artifact** that records it? A decision that exists only in a conversation or a commit message is not recorded. [Traceability, Spec §Deferred Requirements, plan.md Complexity Tracking]
- [ ] CHK029 Is Assumption 3 (*"the schema and access patterns must be the ones that will run in Azure"*) stated in a way that could ever be **checked**? As written it is an intention. requirements.md flagged it in iteration 3 as *"worth an explicit check during planning"*; confirm whether that check happened and where its result is recorded. [Measurability, Assumption 3]

---

## Known Conflicts Requiring a Decision

These were found while writing this checklist and are stated separately because they are not
merely wording issues — they need a human decision, not a rewrite.

### K1 — Single-Entra-tenant implementation versus multi-organisation product intent

**✅ RESOLVED 2026-08-10 — [ADR-019](../../../docs/adr/ADR-019-single-entra-tenant-in-horizon-1.md).**
Option 3 (defer) chosen: Horizon 1 uses one Entra tenant, and **SC-005 has been split** — its
isolation half stays in S2 and must be proven, its multi-directory sign-in half moved to Deferred
Requirements. Rationale: S2's premise is local verifiability, and both alternatives break it —
multi-tenant registration needs a second Entra directory to test, B2B introduces a second
invitation system before the first is built. The seam already exists in the data model, so this is
deferral rather than debt. Entra B2B is recorded as the expected eventual answer.

The original analysis is kept below, unedited, because the hazard it names still applies to whoever
implements the multi-tenant option later.

**Severity when found: HIGH.**

- Spec Assumption 1: *"Users authenticate with existing organisational accounts"* — and the product
  sells to multiple customer organisations (SC-005 requires two independent organisations operating
  concurrently).
- But `infrastructure/scripts/create-entra-app-registrations.sh` creates the API with
  `--sign-in-audience AzureADMyOrg` — **single Entra tenant only**. research.md R2 documents the
  design as single-Entra-tenant.
- Under that configuration, a user from a second customer's Entra tenant **cannot obtain a token at
  all**, so SC-005 cannot be satisfied by real organisational accounts.

The data model is already correct for the multi-tenant case — `User` keys on `(EntraTenantId,
EntraObjectId)` precisely because `oid` is not globally unique. So the *model* anticipates several
Entra tenants while the *app registration* forbids them.

Three coherent resolutions:

1. **Accept single-Entra-tenant for S2** and state it as a scope limit: customer users are guests
   invited into the platform's own Entra tenant (Entra B2B). SC-005 is then satisfied by guest
   accounts, and the spec should say so.
2. **Make the app registration multi-tenant** (`AzureADMultipleOrgs`), which changes issuer
   validation, requires per-tenant admin consent, and needs an explicit allow-list of accepted
   `tid` values — otherwise any Entra tenant in the world can authenticate.
3. **Defer**, and record that S2 proves the model with one Entra tenant while multi-organisation
   sign-in is a later slice.

**Option 2 without a `tid` allow-list would be a security defect**, so whichever is chosen should
be recorded as an ADR rather than settled in code.

### K2 — FR-010 forbids what Story 1 scenario 5 requires

**✅ RESOLVED 2026-08-10.** FR-010 now reads *"without blending their data **within any
tenant-scoped response**"*, with a note that the tenant-list operation is one of ADR-017's three
enumerated exceptions. The contradiction was on the face of the wording only — the design was
already coherent.

### K3 — The Member role has no observable behaviour in this slice

**✅ RESOLVED 2026-08-10.** Assumption 5 now states that Member and Reader have identical effective
permissions in S2 and that this is expected: there is no tenant-scoped *data* to act on until the
delivery model arrives (S11), which is where the distinction becomes observable. The role is
carried and enforced now; Story 3's independent test cannot distinguish the two, and that is
recorded rather than papered over. The assumption explicitly forbids inventing an operation just
to make the distinction testable — that would be building for an anticipated need (Principle X).

---

## Notes

- Check items off as `[x]` only when you can cite the satisfying sentence
- Record findings inline; a finding with no location is not actionable
- **CHK013, CHK019, CHK006, and K1 are the highest-value items here.** The first two are
  requirements that read as testable but are not; CHK006 undermines the evidence for SC-004,
  which permits zero exceptions; K1 may block SC-005 outright
- This checklist reviews the **requirements**. Reviewing the *implementation* against
  research.md R3's ten query-filter bypass paths is a separate artifact — see tasks.md T095
