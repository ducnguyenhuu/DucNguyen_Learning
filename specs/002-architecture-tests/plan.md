# Implementation Plan: Architecture Tests

**Branch**: `002-architecture-tests` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-architecture-tests/spec.md`

## Summary

Turn eleven architectural rules from documented intent into build failures, and clear the one
live violation the new rules expose.

Ten of the eleven gates are new enforcement over code that already exists; the eleventh
(FR-020-FR-022) guards spec 001's requirement coverage from silently rotting. The slice also
carries one production refactor: `Tenancy.Application` currently references
`Microsoft.EntityFrameworkCore` as a NuGet package, which FR-005's gate makes a build failure,
so the dependency is inverted — `Infrastructure` translates EF Core's `DbUpdateException` into
an `Application`-owned type.

**Technical approach, decided by [research.md](research.md)**: no architecture-testing library
is added. NetArchTest was tested first because the project's `testing` skill writes its
slice-3 example in that syntax, and it was rejected on evidence: run against this codebase it
reported one of two structurally identical violations. The gates are built instead from
`.csproj` declaration parsing, source-text scanning, and plain reflection — each chosen per
rule class for what that rule actually asserts.

## Technical Context

**Language/Version**: C# / .NET 10 (SDK 10.0.105 confirmed present)
**Primary Dependencies**: **none new** — and enforced as such: FR-014/FR-017/FR-018 are
implemented as a single pin over the solution's whole package set (see
[spec Clarifications](spec.md#clarifications)), so this slice's own "no new dependency"
property becomes a gate rather than an intention. research.md R1 rejects NetArchTest and
ArchUnitNET
**Storage**: N/A for the gates themselves. FR-019's behavioural test uses the existing SQL
Server Testcontainer already wired into `Tenancy.IntegrationTests`
**Testing**: xUnit v3. New project `tests/ArchitectureTests/` (FR-001); the gates are
ordinary tests, not a build task, so they run under `dotnet test` with everything else
**Target Platform**: local developer machine (macOS arm64 verified); CI is S7, so "fails the
build" means "fails `dotnet test`" in this slice
**Project Type**: single — four source projects under one capability, plus test projects
**Performance Goals**: full suite under 5 minutes (FR-025). Measured baseline entering this
slice: 112 unit + 83 integration tests, ~27s integration / ~0.2s unit
**Constraints**: every gate must name the offending project, package, call site, type, or
requirement (FR-024); every gate must be demonstrated red before acceptance (FR-023)
**Scale/Scope**: 25 functional requirements, 11 gates, 6 user stories, 1 capability, 4 source
projects. Three gates pin the *absence* of something (no second capability, no background job,
no provider SDK) rather than validating an instance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — result unchanged.*

Resolved against the constitution's Principle Gate Checklist. Each principle states compliance
or why it does not apply.

| # | Principle | Resolution |
|---|---|---|
| I | Human approval for production / high-risk AI | **N/A** — no production deployment and no AI in this slice. The two decisions this slice rests on were taken by the project owner, not inferred: inverting the EF Core dependency, and implementing ADR-008/009's gates here rather than at S13 |
| II | Relevant ADRs identified; conflicts proposed not worked around | **Complies.** ADR-021 was written and accepted rather than the patterns being adopted or skipped silently, and the spec was amended when ADR-021 named S3 as its enforcement point. ADR-013 (raw SQL, background jobs), ADR-001/008/009 (provider SDK, model naming), and ADR-003 (capability boundaries) are each mapped to a gate. Research.md R2 proposes a spec amendment openly rather than quietly building something different |
| III | Service and data boundaries respected | **Complies and strengthens.** FR-008 is the gate for this principle; FR-009 pins that only one capability exists so a second is a visible decision |
| IV | Tenant isolation enforced and tested | **Complies and strengthens.** FR-010-FR-013 close both U12 gaps that Principle IV's enforcement depends on — raw SQL and tenant-context-less background jobs. This slice adds no tenant-scoped operation of its own, so there is no new operation needing an isolation test |
| V | No stored credentials; authorization per request | **N/A** — no credential handling and no new endpoint. FR-006's refactor touches `EnsureUserProvisioned`, which is on the auth path, so its behaviour must be preserved by test (FR-007a) rather than assumed |
| VI | Correlated telemetry, health, audit, AI cost | **N/A** — observability is S4. FR-006's refactor must not remove existing logging from the paths it touches; no new telemetry is added |
| VII | Automated gates cover the boundaries this work touches | **This slice *is* Principle VII.** Eleven gates; FR-023 additionally requires each be proven capable of failing, closing the "gate that could never fail" loophole the `testing` skill names as a red flag |
| VIII | Deterministic solution before any AI capability | **N/A** — no AI capability. FR-014/FR-015 enforce the boundary that keeps it that way |
| IX | AI consumed only through the abstraction; spend attributable | **Complies in advance.** FR-014 (no provider SDK outside AI Platform) and FR-015 (no model name outside AI Platform config) are the gates ADR-008 and ADR-009 asked for. Both pass trivially today and pin absence (FR-016) |
| X | Delivered as a working, tested, deployed, end-to-end slice | **Partial — justified in [Complexity Tracking](#complexity-tracking).** This slice does not exercise entry point → persistence → telemetry, because its deliverable is enforcement over code already shipped in S2 |
| XI | No individual-level measurement; personal data minimized | **N/A** — no measurement of people, no personal data. The gates read `.csproj` files, source text, and assembly metadata |

**Gate result**: PASS with one justified partial (Principle X). No unjustified violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-architecture-tests/
├── spec.md              # 25 FRs, 6 SCs, 6 user stories
├── plan.md              # This file
├── research.md          # Phase 0 — mechanism decision + 1 spec amendment
├── quickstart.md        # Phase 1 — running the gates, and proving each can fail
├── checklists/
│   └── requirements.md  # Spec quality + ADR-021 consistency check
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

No `data-model.md` and no `contracts/` are generated for this slice. There is no entity and
no API surface: the deliverable is test code plus one dependency inversion. Creating empty
placeholders would be the scaffolding-without-content that the `architecture` skill and
Principle X rule 5 both reject.

### Source Code (repository root)

```text
src/Tenancy/
├── Tenancy.Domain/               # unchanged by this slice
├── Tenancy.Application/          # FR-006: EF Core package reference removed;
│                                 #   DbUpdateException catches replaced with an
│                                 #   Application-owned exception type
├── Tenancy.Infrastructure/       # FR-006: translates DbUpdateException at the boundary
└── Tenancy.Api/                  # FR-019: ProblemDetailsHandler gains central
                                  #   DomainException -> 400, ConflictException -> 409

tests/
├── ArchitectureTests/            # NEW (FR-001) — all eleven gates live here
│   ├── LayeringGates.cs          #   FR-004, FR-005
│   ├── CapabilityBoundaryGates.cs#   FR-008, FR-009 (migrated from Tenancy.UnitTests)
│   ├── RawSqlGates.cs            #   FR-010, FR-011
│   ├── BackgroundJobGates.cs     #   FR-012, FR-013
│   ├── DependencyPinGates.cs     #   FR-014, FR-017, FR-018 — ONE pinned package set
│   │                             #     (clarified: a deny-list cannot enumerate "equivalent")
│   ├── ModelNamingGates.cs       #   FR-015, FR-016
│   ├── RequirementCoverageGates.cs#  FR-020, FR-021, FR-022
│   └── Support/                  #   csproj parsing, source scanning, allow-lists
├── Tenancy.UnitTests/            # Architecture/ folder removed (FR-002 migration)
└── Tenancy.IntegrationTests/     # FR-019's behavioural test
```

**Structure Decision**: A dedicated `tests/ArchitectureTests/` project, matching the layout
the project's `testing` skill specifies. The five existing tests move out of
`tests/Tenancy.UnitTests/Architecture/`, which is the wrong home — that project is for
domain and application logic with no I/O, and these gates read files from disk.

`ContractTests/` and `EndToEndTests/` from the same standard layout are deliberately **not**
created (FR-003): their first real consumers are S9 and S7.

`ArchitectureTests` references all four source projects. That is intentional and does not
violate the rules it enforces — the gates are the one legitimate reader of the whole graph,
and FR-008's rule is scoped to projects outside the `Tenancy.*` family under `src/`.

## Implementation Sequencing

The order is forced in two places and otherwise free:

1. **FR-001/FR-002 first** — create `ArchitectureTests`, migrate the five existing tests
   unchanged, confirm they still pass. Everything else lands in this project.
2. **FR-007a before FR-006** — `EnsureUserProvisioned`'s get-or-create race has no test
   today (verified: no dedicated test file, and the method's own doc comment concedes "no
   integration test harness yet"). Its test is written and seen to pass against the current
   `DbUpdateException` behaviour *before* the refactor touches that catch block. Refactoring
   first would mean changing untested code and reporting the result as verified.
3. **FR-005's gate after FR-006's refactor** — or the build is red for the whole slice.
   `InviteMember`'s path already has a test (`InviteMemberTests.cs:176` injects a
   `DbUpdateException` via a fake), so only its injected type changes.
4. Remaining gates are independent and can land in any order.

Each gate carries its own red-first proof (FR-023). For the three absence-pinning gates the
proof requires temporarily introducing the thing being forbidden — a second capability, a
background job, a provider SDK package — then reverting. FR-012's is the notable one: it has
no positive case at all while no background job exists, so its proof is an explicit, reverted
fixture rather than a permanent test.

## Complexity Tracking

> Filled because the Constitution Check records one partial.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle X** — the slice is cross-cutting, not a vertical entry-point-to-telemetry slice | The roadmap schedules S3 here deliberately, and its own reasoning is that retrofitting boundaries after violations accumulate is far more expensive. The violation this slice already found — `Tenancy.Application` depending on EF Core, invisible to S2's tests — is the evidence: it shipped, passed review, and passed a green suite | Folding these gates into a later feature slice was the alternative. Rejected because each subsequent slice adds code the gates were meant to constrain, so the gates arrive after the violations they exist to prevent. Note the letter of Principle X is missed but its stated prohibition is not: it forbids "horizontal layers spanning many months without a deployment", and this is one week of hardening over code already deployed, including one real production refactor (FR-006) |
| **FR-019 amended from a structural gate to central mapping** | Detecting "this handler could let a `DomainException` escape" is a method-body dataflow question. The only mechanism that answers it reliably is a Roslyn analyzer — a separate build-integrated project for one convention | Building the analyzer was rejected as disproportionate, and it would leave `ProblemDetailsHandler`'s blanket `500` as the underlying defect regardless. Central mapping removes the failure mode instead of gating it, which is the stronger form of Principle VII. Recorded openly in research.md R2 rather than substituted silently |

## Phase Status

- [x] **Phase 0** — research complete: [research.md](research.md). One open question
      (enforcement mechanism) resolved empirically; one spec amendment raised (FR-019)
- [x] **Phase 1** — design complete: [quickstart.md](quickstart.md). No `data-model.md` or
      `contracts/`, with the reason recorded above
- [x] Constitution Check re-evaluated post-design — result unchanged, PASS with one
      justified partial
- [ ] **Phase 2** — `/speckit.tasks` (not run by `/speckit.plan`)
