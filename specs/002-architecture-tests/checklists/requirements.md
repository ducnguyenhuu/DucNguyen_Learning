# Specification Quality Checklist: Architecture Tests

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-15
**Last validated**: 2026-08-15, after `/speckit.clarify` (spec is now at 25 FRs)
**Feature**: [spec.md](../spec.md)

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

## Verification Performed

Claims in this spec were checked against the codebase rather than assumed. Recorded here
because the first draft's failures were all overclaims:

| Claim | How verified | Result |
|---|---|---|
| No background job exists | `grep` for `IHostedService`/`BackgroundService`/`AddHostedService` across `src/` + `tests/` | 0 occurrences ✅ |
| Exactly one audited raw-SQL call | `grep` for all `FromSql*`/`ExecuteSql*` forms | 1 hit, `MembershipRepository.cs:100` ✅ |
| No model provider SDK referenced | Full package list from all `.csproj` + `Directory.Packages.props` | 13 packages, none a provider SDK ✅ |
| `Tenancy.Domain` depends on nothing | Read `Tenancy.Domain.csproj` | Zero project *and* package references ✅ |
| `Tenancy.Application` violates layering | Read `Tenancy.Application.csproj` | `<PackageReference Include="Microsoft.EntityFrameworkCore" />` present ✅ |
| Scope of that violation | `grep` for `DbUpdateException` in `src/` | 3 sites in Application, not 1 as the csproj comment claims ✅ |
| Which race paths are tested | `grep` for `DbUpdateException` in `tests/` | `InviteMember`'s is covered; `EnsureUserProvisioned`'s is **not** ✅ |
| spec 001 has 26 live FRs | Counted `FR-0NN` definitions in spec 001 | 26 (FR-001..FR-026) ✅ |
| spec 001 defers work to S3 | Read spec 001's Deferred Requirements table | `old-FR-028`, `old-SC-008` both S3-assigned ✅ |
| Numbering integrity of this spec | Enumerated all FR/SC definitions and cross-references | FR-001..FR-025, SC-001..SC-006, no gaps or duplicates; all spec-001 references explicitly qualified ✅ |

## Clarification session (2026-08-15, post-plan)

`/speckit.clarify` was run **after** `/speckit.plan` rather than before it, so its four answers
required propagating back into `plan.md` and `research.md`. Ordering noted as a process cost:
run clarify first next slice.

Two of the four closed gaps the spec had explicitly deferred to planning and planning had not
actually resolved:

| Gap | Resolution | Impact if left open |
|---|---|---|
| "Model provider SDK" / "model identifier string" undefined — spec deferred them to planning; planning never enumerated them | FR-014/FR-017/FR-018 enforced by one pin over the whole package set; FR-015 fixed to `src/**/*.cs` and six explicit prefixes | FR-014 and FR-015 were **not implementable as written** |
| FR-012 named "an abstraction whose contract establishes tenant context first" — no such abstraction exists in the codebase | Prohibition only; no replacement built, shape belongs to S8/S10's first consumer; gate must state what to do instead | FR-012 described a path nobody could take |
| FR-012's "tenant-scoped repository" did not partition the ports cleanly (`IUserRepository` documents itself as *not* tenant-scoped; `IMembershipDirectory` is the sanctioned cross-tenant one) | Every persistence port, identified mechanically by implementation namespace; `ITenantContext` excluded | Gate scope ambiguous — would either miss violations or block legitimate use |
| FR-015 scope unbounded — this repo names models throughout docs, specs, and commit trailers | `src/**/*.cs` only | Gate would fail on the repository's own prose on first run |

## Amendments from planning (Phase 0)

| Requirement | Change | Driver |
|---|---|---|
| FR-019 | Structural gate → central exception-to-status mapping in `ProblemDetailsHandler`, proven by test | [research.md](../research.md) R2: the structural form needs a Roslyn analyzer, and central mapping removes the failure mode rather than gating it |

The mechanism question this checklist left open for planning is resolved: **no
architecture-testing library is added.** NetArchTest was tested first (the `testing` skill
writes its slice-3 example in that syntax) and rejected on evidence — run against this
codebase it reported one of two structurally identical violations. See research.md R1.

## Consistency with higher-authority documents

Principle II places ADRs above specs, so the spec must not contradict or lag an ADR that
names it. Checked after ADR-021 was accepted:

| ADR-021 ruling | Spec 002 coverage | Status |
|---|---|---|
| 1 — no validation library | FR-017 | ✅ enforced |
| 2 — no mediator/dispatcher | FR-018 | ✅ enforced |
| 3 — no separate read model | *deliberately none* | ✅ correct — ADR records it as not mechanically checkable with one context; a gate here could never fail |
| Known weakness: `DomainException` → 4xx convention unenforced | FR-019 | ✅ closed |
| Negative consequence: domain/schema length drift | Fixed outside this spec, own commit | ✅ closed |

## Notes

- This slice's "user" is the developer working in the repository, not an end user — stated
  explicitly in the spec's opening paragraph, since the template's language otherwise
  assumes a customer-facing feature.
- Some requirements name concrete types (`IHostedService`, `DbUpdateException`,
  `TenancyDbContext`) and specific packages. This is deliberate and not an implementation
  leak: the requirement *is* about those specific boundaries, and naming them is what makes
  the requirement testable. The enforcement *mechanism* was left open for planning and is now
  decided — see research.md R1 (no library; declaration parsing, source scanning, reflection).
- Two decisions were taken by the project owner during review and are recorded in the spec
  rather than left open: (1) `Tenancy.Application`'s EF Core dependency is inverted, not
  allow-listed; (2) ADR-008/ADR-009's gates are implemented in this slice rather than
  deferred to S13.
- All checklist items pass. `/speckit.plan` and `/speckit.clarify` are both complete; next is `/speckit.tasks`.

## Resolved: did the enforcement mechanism warrant an ADR?

This checklist previously left that question open for planning. **Answer: no ADR needed.**
An ADR records a decision that constrains future work; this one resolved to *keeping* the
approach S2 already uses (`.csproj` parsing) and adding no dependency, so there is no new
constraint to record and nothing for a future reader to be bound by. The evidence for
rejecting NetArchTest is in research.md R1, which is where a reader looking at these gates
will already be.

Revisit if a future slice needs type-level IL analysis that declarations cannot express —
adopting a library at that point *would* be an ADR-worthy decision.
