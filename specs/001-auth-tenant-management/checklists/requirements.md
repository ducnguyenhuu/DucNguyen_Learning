# Specification Quality Checklist: Authentication & Tenant Management

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-08
**Revalidated**: 2026-08-08 — after narrowing to slice S2 · **2026-08-09** — after planning (iteration 4)
**Feature**: [spec.md](../spec.md)
**Roadmap slice**: S2 — Auth + Tenant + Persistence (local)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Slice Discipline *(added after narrowing)*

- [x] The spec covers exactly one roadmap slice
- [x] Every deferred requirement names its target slice
- [x] Nothing deferred is silently dropped — all recorded in Deferred Requirements
- [x] The slice is completable and verifiable without work from a later slice
- [x] Dependencies reflect only what this slice actually needs

## Validation Notes

**Iterations 1–2 (initial draft).** Two items failed and were fixed:

- *No implementation details* — FRs named Microsoft Entra ID, Azure SQL, AKS, and
  OpenTelemetry directly. Restated as capabilities; concrete technology choices
  moved to Assumptions.
- *Success criteria technology-agnostic* — criteria referenced millisecond latency
  and scanning-tool output. Restated as user-facing and review-based outcomes.

No [NEEDS CLARIFICATION] markers were needed; every gap had a defensible
industry-standard default, all recorded in Assumptions.

**Iteration 3 (narrowing to S2).** The spec previously spanned roadmap slices
S2–S7: its Story 4 contained the entire Azure delivery path — telemetry,
containerization, Terraform/AKS provisioning, and CI/CD — behind four acceptance
scenarios, representing roughly six slices of work. This failed the newly added
Slice Discipline section and violated `idea.md` §29.

Changes made:

- Story 4 removed in full. Its content is now roadmap slices S3–S7.
- FR count reduced from 31 to 26, renumbered contiguously. FR-023 (data ownership)
  was retained and renumbered; FR-024/025/026 are new, narrowed forms of
  requirements that would otherwise have been lost entirely — see below.
- Success criteria reduced from 12 to 9, dropping the four that could only be
  verified after deployment.
- Audit Entry removed from Key Entities; it belongs with S4's audit log.
- Dependencies corrected: **no Azure subscription is required for this slice.**
  That was a false prerequisite that would have blocked work unnecessarily.
- A Deferred Requirements table was added mapping every removed FR and SC to its
  target slice, with original numbering preserved so the future spec can adopt
  them verbatim.

**Deliberate partial retentions.** Three requirements were narrowed rather than
deferred wholesale, because deferring them entirely would have been wrong:

- **FR-024** (domain must not depend on infrastructure) — the *automated gate* is
  S3, but the code must satisfy the boundary while it is being written. Deferring
  the constraint along with its enforcement would guarantee violations to clean up.
- **FR-025** (structured logging of security-significant events) — correlated
  tracing and the immutable audit store are S4, but developing without any logging
  is not workable, and silently dropping all record of authorization refusals for
  a slice would be a poor default.
- **FR-026** (no secrets in source control) — runtime retrieval via managed
  identity is S6, but a secret committed once must be treated as compromised
  forever. This cannot wait for S6.

All items pass after iteration 3.

## Reviewer Attention

Judgement calls most worth disagreement before planning:

1. **Assumption 4 keeps the full §17 AKS target for S6.** This is the largest cost
   in Horizon 1 (~3–4 weeks, ~$700–1,500/month) and was chosen deliberately over a
   lighter start, per `idea.md` §59.2. It no longer burdens *this* slice, which is
   the main benefit of the narrowing.
2. **Assumption 7 (one-hour revocation window)** is a real security trade-off: a
   removed member retains access for up to an hour. Acceptable at this scale; worth
   tightening before a security-sensitive customer.
3. **Assumption 3 requires the local schema to be the one that will run in Azure.**
   If this drifts, S6 becomes a rewrite rather than a deployment. Worth an explicit
   check during planning.
4. ~~**SC-003 (50 concurrent users across 20 tenants)** must be verified locally~~ —
   **superseded 2026-08-09.** Verification is deferred to **S7**
   ([traceability U6](../../../docs/traceability.md#u6--22-lists-eight-test-types-only-four-are-scheduled)).
   The reviewer note above was wrong on one point: a local pass is not merely
   "necessary, not sufficient" — on this machine it is close to meaningless, because
   the local database is SQL Server under x86 emulation on ARM. The requirement still
   constrains this slice's indexing and query shape; only the load test moves.
5. **Non-Goals remain aggressive** — no UI beyond what demonstrates the acceptance
   scenarios, no tenant deletion, no data export. Confirm no stakeholder expects a
   demo-able interface from this slice.

## Iteration 4 — post-planning consistency review (2026-08-09)

Re-validated after `/speckit.plan`, ADR-017, ADR-018, and the SC-003 deferral. All
checklist items still pass. Six inconsistencies were found and fixed — full list in the
spec's [Post-Planning Review](../spec.md#post-planning-review). The one worth calling out
here is a **quality defect this checklist did not catch in iterations 1–3**: the Deferred
Requirements table reused FR-023..FR-026 and SC-006..SC-009 for entirely different
requirements than the live ones, which would have misled whoever adopted them in S3–S7.

**Checklist gap identified.** "Requirements are testable and unambiguous" was ticked, but
nothing in this checklist asks whether *identifiers* are unambiguous. Worth adding to the
template if another spec ever renumbers.

Also confirmed, and more reassuring than the fixes: **changing the telemetry backend
(ADR-018) and fixing tenant-context resolution (ADR-017) required no functional requirement
to change.** Both were absorbed by ADRs beneath the specification, which is where
implementation decisions belong.

## Blocking Prerequisite

~~The ADR framework and ADR-001, ADR-002, ADR-003 do not yet exist.~~
**✅ Resolved 2026-08-08** — roadmap S1 delivered the framework, template, and twelve ADRs.
All three were cited during planning, and ADR-017 was raised by this slice's planning.

**Remaining blocker (2026-08-09):** a **Microsoft Entra ID tenant with app-registration
rights**, and the two registrations described in [quickstart.md](../quickstart.md) §1. Needs
a human. No Azure subscription required.
