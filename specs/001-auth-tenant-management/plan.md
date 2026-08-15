# Implementation Plan: Authentication & Tenant Management (S2)

**Branch**: `001-auth-tenant-management` | **Date**: 2026-08-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-auth-tenant-management/spec.md`
**Roadmap slice**: [S2 — Auth + tenant + persistence](../../roadmap.md) · 2–3 weeks

## Summary

Build the Tenancy service: Entra ID authentication, tenant CRUD, membership, invitations,
three roles, and tenant-isolated persistence — verifiable **on a development machine**, with
no Azure.

Technical approach: one service (`Tenancy`) in four Clean Architecture projects per ADR-003
and ADR-002. Isolation rests on an EF Core 10 **named** global query filter applied by model
iteration, plus a `SaveChangesInterceptor` closing the write side that query filters do not
cover. Tenant context resolves from a **validated route selector** — the decision this plan
had to escalate to an ADR (see below). Integration tests run against real SQL Server in
Testcontainers, because an in-memory provider cannot catch a broken query filter, which is
the one bug that matters most here.

**Planning surfaced one conflict and three gaps. None is worked around silently:**

| Finding | Status |
|---|---|
| ADR-013 and the `security` skill do not specify how a user in multiple tenants selects one — and the skill's absolute wording forbids the only mechanism that satisfies FR-010 | ✅ **Resolved 2026-08-09** — [ADR-017](../../docs/adr/ADR-017-tenant-context-resolution.md) **Accepted**; `security` skill amended to distinguish *selector* from *grant* |
| SC-003 (95% of reads < 1s at 50 concurrent users) needs a load test, which [U6](../../docs/traceability.md) records as unscheduled | ✅ **Resolved 2026-08-09** — verification deferred to **S7**, recorded in spec Deferred Requirements, U6, and S7's *Done when* |
| SC-001/SC-002 measure a user interface that is out of scope for S2 | Proxy measurement via [quickstart.md](quickstart.md); the "without documentation" clause stays unverified |
| Principles VI and X cannot be fully satisfied by a local-only slice | Recorded as accepted, roadmap-sanctioned deviations — see Complexity Tracking |

## Technical Context

**Language/Version**: C# 14 / .NET 10 LTS
**Primary Dependencies**: ASP.NET Core 10, EF Core 10, Microsoft.Identity.Web 4.14.2
**Storage**: SQL Server 2022 (container)
**Testing**: xUnit v3, Testcontainers.MsSql, Respawn
**Target Platform**: Linux / macOS ARM64 development machine
**Project Type**: single backend service (REST API)
**Performance Goals**: 95% of tenant reads under 1s at 50 concurrent users across 20 tenants
**Constraints**: no Azure, no OpenTelemetry, no messaging, no AI in this slice
**Scale/Scope**: tens of tenants, hundreds of users

Detail and rationale behind each line:

| Line | Notes |
|---|---|
| Runtime | .NET 10 LTS, supported to Nov 2028 (ADR-002 requires current LTS). Installed: 10.0.105 |
| Auth | Microsoft.Identity.Web over raw `JwtBearer` — it configures `Microsoft.AspNetCore.Authentication.JwtBearer` 10.0.10 with Entra-correct issuer/audience validation rather than leaving those hand-rolled ([research.md](research.md) R2) |
| Storage | `mcr.microsoft.com/mssql/server:2022-latest`. Schema and access patterns are the ones that will run on Azure SQL, so S6 is a deployment exercise rather than a rewrite (spec Assumption 3). **Not** `2025-latest` — it crashes under Rosetta on Apple Silicon (R5) |
| Testing | xUnit v3 3.2.2 · Microsoft.AspNetCore.Mvc.Testing 10.0.10 (must match ASP.NET Core exactly) · Testcontainers.MsSql 4.11.0 · Respawn 6.2.1. **Not** FluentAssertions 8+ — licence changed to commercial (R9) |
| Platform | Azure is S6. This slice is verifiable on a development machine, by design |
| Project type | No frontend — none is in MVP scope (`idea.md` §46a), and no framework has been chosen for one |
| Performance | SC-003. **Verification deferred to S7** (see Complexity Tracking); the requirement still constrains indexing and query shape here |
| Constraints | OpenTelemetry S4 · container image S5 · messaging S8 · zero AI (spec Assumption 10, `idea.md` §47) · full suite under 5 min (SC-006) |
| Scale | Spec Assumption 9 — enough to prove the model, not to serve a market |

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 — result below is post-design.*

Resolved against the [Principle Gate Checklist](../../.specify/memory/constitution.md).

| # | Principle | Verdict | How |
|---|---|---|---|
| **I** | Human authority over intent, architecture, risk | ✅ | No production exists yet, so the deployment clause is inert. ADR-017 was architecturally significant, so it was filed as `Proposed` and **approved by the project owner (2026-08-09)** before implementation — not assumed. |
| **II** | Architectural authority is hierarchical | ✅ | ADR-002/003/013 read and honoured. The one conflict found (skill stricter than ADR) was **raised and amended, not coded around** — ADR-017 Accepted, and the `security` skill's wording corrected in the open. |
| **III** | Business-capability boundaries, explicit data ownership | ✅ | One service, one database, one bounded context (Tenancy). Domain layer has no outward dependency. No other context exists yet to couple to. |
| **IV** | Tenant isolation is non-negotiable | ✅ | Four mechanisms per ADR-013: named global filter by model iteration; context resolved once per request from validated membership; role authorization against that membership; isolation test per tenant-scoped operation. The **three** non-tenant-scoped operations are enumerated in ADR-017 and individually tested. Bypass list documented ([research.md](research.md) R3). |
| **V** | Secure by default | ✅ | Entra ID, no passwords stored (FR-001). The API holds **no client secret** — it only validates tokens. User Secrets locally; Key Vault is S6. Invitation tokens stored as SHA-256 hashes only. 401/403/404 distinctions per FR-009/FR-018. |
| **VI** | Observable by default | ⚠️ **Partial — accepted deviation** | Structured logging for every auth outcome, tenant mutation, membership change, and authorization refusal (FR-025). Correlated tracing, metrics, health, and the immutable audit store are **S4**. See Complexity Tracking. |
| **VII** | Automated gates, not reviewer vigilance | ⚠️ **Partial — sequenced** | Unit + integration tests, isolation tests per operation, `has-pending-model-changes` in the build, warnings-as-errors, nullable-as-errors. **Architecture tests are S3 by design** — the code must satisfy the boundaries now (FR-024) but the gate lands one slice later. Roadmap S3 exists precisely so this is not indefinite. |
| **VIII** | Deterministic first — AI must earn its place | ✅ **N/A by design** | Zero AI in this slice (spec Assumption 10, `idea.md` §47). Nothing here is a candidate. |
| **IX** | AI provider abstraction, cost accountability | ✅ **N/A** | No AI. Per Principle IX's own final rule, the seam is not built before it has a consumer — that is S13. |
| **X** | Vertical slices deliver working software | ⚠️ **Partial — accepted deviation** | End-to-end from HTTP to persistence, tested. But **not deployed to a real environment** — S2 is deliberately local. This is the plan's largest constitutional tension. See Complexity Tracking. |
| **XI** | Measure systems, never rank individuals | ✅ | No metrics about people. Personal data limited to what invitations and display require: email, display name, Entra identifiers. No profiling, no activity tracking. |

**Gate result: PASS with three recorded deviations and one blocking prerequisite (ADR-017
approval).** No deviation is undocumented, and each has a named slice that closes it.

## Project Structure

### Documentation (this feature)

```text
specs/001-auth-tenant-management/
├── plan.md              # This file
├── research.md          # Phase 0 — 10 decisions, incl. the ADR-017 escalation
├── data-model.md        # Phase 1 — entities, isolation classification, EF configuration
├── quickstart.md        # Phase 1 — run it, and walk the refusals
├── contracts/
│   └── openapi.yaml     # Phase 1 — OpenAPI 3.1
├── checklists/
│   └── requirements.md  # pre-existing
└── tasks.md             # Phase 2 — /speckit.tasks, NOT created here
```

### Source Code (repository root)

```text
src/Tenancy/
├── Tenancy.Domain/            # entities, value objects, invariants — NO package references
│   ├── Tenants/               #   Tenant, TenantStatus, TenantSettings,
│                              #   TenantAdministration (the last-administrator invariant,
│                              #   which spans all memberships so it cannot live on one)
│   ├── Users/                 #   User
│   ├── Memberships/           #   Membership, Role, MembershipStatus
│   ├── Invitations/           #   Invitation, InvitationStatus
│   └── Abstractions/          #   ITenantOwned, IClock, DomainException
├── Tenancy.Application/       # use cases, DTOs, port interfaces
│   ├── Tenants/ Members/ Invitations/
│   └── Abstractions/          #   ITenantContext, repository ports
├── Tenancy.Infrastructure/    # EF Core, interceptors, migrations
│   ├── Persistence/           #   TenancyDbContext, IEntityTypeConfiguration<T> per entity
│   ├── Persistence/Interceptors/  # TenantSaveChangesInterceptor
│   ├── Persistence/Audited/   #   THE cross-tenant helper — one file, one method
│   └── Migrations/
└── Tenancy.Api/               # endpoints, DI, middleware, auth
    ├── Endpoints/
    ├── Middleware/            #   TenantContextResolution (ADR-017 — the single seam)
    └── Idempotency/

tests/
├── Tenancy.UnitTests/         # domain invariants, no I/O
└── Tenancy.IntegrationTests/
    ├── Isolation/             #   one test per tenant-scoped operation (SC-004)
    ├── Scenarios/             #   the 15 acceptance scenarios
    └── Infrastructure/        #   SqlServerFixture, TestAuthHandler, ApiFactory

Directory.Build.props          # nullable + warnings-as-errors, once for all projects
Directory.Packages.props       # central package management — one version per package
DeliveryIntelligence.slnx      # .NET 10 XML solution format
.editorconfig
```

**Structure Decision**: one service, four projects, per ADR-003 (Platform/Tenancy is the
first service, justified as a security boundary) and the `dotnet-enterprise` skill's layout.
Dependencies point inward: `Api → Application → Domain`, `Infrastructure → Domain`.
`Tenancy.Domain` carries **no package references** beyond the base library — if EF Core is
ever needed there, the answer is an interface in Domain implemented in Infrastructure.

Two structural choices worth naming because they are security controls, not organisation:

- **`Persistence/Audited/`** holds the single method that bypasses the tenant filter (ADR-017
  exception 2, `GET /tenants`). Putting it in a named directory with one occupant makes the
  exception visible in a file tree and gives S3's architecture test something specific to
  assert against. An exception that is easy to find is an exception that stays reviewed.
- **`Middleware/TenantContextResolution`** is the *only* place `{tenantId}` is read. An
  endpoint resolving its own tenant context is a defect (ADR-017 Compliance).

**Not created, deliberately** (Principle X — a slice must not build for anticipated needs):
`Tenancy.Contracts` (no second service to consume it until S9) · `ArchitectureTests` (S3) ·
`ContractTests` (S9) · `EndToEndTests` (S7+) · `Dockerfile`/compose (S5) · anything under
`infrastructure/terraform` (S6).

## Phase Outputs

**Phase 0 — complete**: [research.md](research.md). Ten decisions, all `NEEDS CLARIFICATION`
resolved or escalated. The three that would have cost the most if guessed:

- `oid` alone is **not** globally unique across Entra tenants — the stable identity is the
  composite `(tid, oid)`. Keying on `oid` would be a latent bug appearing only with a B2B
  guest or a second Entra tenant.
- EF Core's global query filter is bypassed by `Find`/`FindAsync` **by design**, and does not
  apply to writes at all. Both need explicit countermeasures, not trust.
- SQL Server 2025 RTM crashes under Docker Desktop on Apple Silicon (AVX under Rosetta).
  Pin `2022-latest`; Azure SQL Edge, the old ARM workaround, was retired in Sep 2025.

**Phase 1 — complete**: [data-model.md](data-model.md) · [contracts/openapi.yaml](contracts/openapi.yaml) ·
[quickstart.md](quickstart.md).

One design finding worth surfacing from Phase 1: the last-administrator invariant (FR-015)
**cannot** be expressed as a database constraint, and two administrators concurrently removing
*different* administrators could both observe a count of two and both succeed under
`READ COMMITTED`. data-model.md states the mitigation and requires a **concurrent-removal
integration test** — a unit test cannot demonstrate this class of bug.

## Complexity Tracking

Three deviations from the constitution, and one unresolved criterion. All are roadmap-
sanctioned rather than convenient, and each names the slice that closes it.

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **Principle X** — slice is not deployed to a real environment | Roadmap sequences Azure at S6 and budgets it at 3–4 weeks and ~$700–1,500/month (ADR-007). Delivering S2 through Azure first would fold six slices into one, which is exactly the "large incomplete technical layer" `idea.md` §29 prohibits and which this spec was already narrowed to avoid. | Deploying S2 to Azure now was rejected because it front-loads the most expensive, highest-friction slice before the domain model has been proven locally — inverting the roadmap's whole risk ordering. **Gate 1 blocks Horizon 2 until S2–S8 all complete**, so this is deferred, not dropped. |
| **Principle VI** — no correlated traces, metrics, health, or audit store | Observability is S4. FR-025 keeps the non-negotiable part in S2: structured logging of every auth outcome, tenant mutation, membership change, and authorization refusal. | Adding OpenTelemetry now was rejected because S4's proof is *diagnosing an induced failure from telemetry alone in under 10 minutes* — that requires instrumenting real request paths, which must exist first. Doing it here would mean instrumenting twice. |
| **Principle VII** — architecture tests land in S3, not S2 | The boundaries must hold in code now (FR-024); the automated gate is S3, which the roadmap deliberately places early ("retrofitting boundaries after violations accumulate is far more expensive"). | Writing architecture tests in S2 was rejected only on ordering, not merit: S3 is one week and immediately next. The risk window is one slice, and the code being reviewed against the boundary in the meantime is the compensating control. |

**Resolved 2026-08-09:**

| Item | Decision |
|---|---|
| **SC-003** (95% of reads under 1s at 50 concurrent users / 20 tenants) | **Verification deferred to S7**, added to S7's *Done when* and recorded in [U6](../../docs/traceability.md#u6--22-lists-eight-test-types-only-four-are-scheduled). S7 is the earliest slice with both a pipeline to run a load test and a deployed environment to run it against, and is still before Gate 1. Measuring in S2 was rejected because S2's database is SQL Server under x86 emulation on an ARM machine — the number would say nothing about Azure SQL. **The requirement still constrains this slice's design** (indexing, query shape); only the proof moves. |

**Still open — accepted as a known limitation:**

| Item | Status |
|---|---|
| **SC-001 / SC-002** (time-to-first-tenant under 5 min, "without documentation") | Both measure a UI that S2 does not build. Measured as a proxy along the API path via [quickstart.md](quickstart.md) §6, with the real number recorded. The **"without documentation" clause remains unverified** until a UI exists — stated rather than quietly counted as passing. |

## Post-Implementation Corrections (SC-009)

Per Principle II, a recorded decision that turned out to be wrong is corrected in the open,
not silently worked around. This section names what `plan.md`, `research.md`, or an ADR
assumed, what implementation actually found, and how it was resolved — drawn from
`.superpowers/sdd/tasks/progress.md`, the SDD execution ledger for T010–T096, which is the
authoritative account of what happened and should be read for full detail. Added at T097,
the plan's final task.

| # | Assumed / planned | Actually found | Resolution |
|---|---|---|---|
| 1 | `research.md` R3 item 4: "`ExecuteSqlRaw`, `SqlQuery<T>`, any raw SQL: None in this slice." | T075 legitimately introduced one `ExecuteSqlInterpolatedAsync` call (a row-locking `SELECT ... WITH (UPDLOCK, HOLDLOCK)`) for the last-administrator race-safety mechanism — reviewed and accepted at the time, but the research doc's text was never updated. | `research.md` R3 item 4 corrected in place (this same change set) to describe the call site instead of denying its existence. |
| 2 | Neither `plan.md` nor `research.md` anticipated a "silent `SaveChanges` skip": EF Core marks an entry `Unchanged` (and skips the `UPDATE` entirely) if pinning `RowVersion.OriginalValue` is the *only* thing that changed on an otherwise-unmodified entry — so a stale/racing `If-Match` can silently "succeed" instead of hitting the optimistic-concurrency check. | Found twice: first in T087's own new code (`MemberEndpoints.cs`), then found to **already exist**, unnoticed, in Phase 3's shipped and previously-reviewed `TenantEndpoints.cs` (T058) — a real, exploitable FR-021 violation that had passed review earlier in the project. | Both call sites fixed by explicitly marking the entry `EntityState.Modified` before save, so the `RowVersion` concurrency token is always evaluated. See **[ADR-020](../../docs/adr/ADR-020-ef-core-rowversion-pinning-requires-explicit-modified-state.md)** for the reusable lesson — this is an EF Core behavior worth knowing about in any future slice that uses optimistic concurrency, not just this one. |
| 3 | ADR-017 reasons that tenant-context resolution must be an `IEndpointFilter` (route values are only available post-routing) but does not discuss how that interacts with ASP.NET Core's authorization middleware ordering. | Discovered at T085/T088: an `IEndpointFilter` runs *after* `UseAuthorization()`'s `AuthorizationMiddleware`. A conventional `[Authorize(Policy=...)]` attribute would therefore evaluate a role-based policy *before* `ITenantContext.Role` is ever populated, failing closed for the wrong reason on every request. | T088 evaluates the policy explicitly via `IAuthorizationService.AuthorizeAsync` from within a filter chained *after* tenant-context resolution, rather than via the `[Authorize]` attribute path. This pipeline-ordering constraint was not previously documented anywhere; it is documented here and in T085/T088's ledger entries as the reasoning for that design choice. No ADR amendment judged necessary — it is an implementation consequence of ADR-017's existing decision, not a new decision or a reversal of one. |
| 4 | Several pieces of test infrastructure were built early but assumed (implicitly, by omission) to already be fully wired: `ApiFactory.ResetDatabaseAsync()` (built early, never called between tests until a Phase 6 fix, producing genuinely non-deterministic integration-test flakiness for several phases); `TestAuthHandler` never surfaced an `X-Test-Email` header as an `"email"` claim, needed by `AcceptInvitation`'s identity-match check since T063 but undiscovered until Phase 6; `SignedTokenHarness.MintToken` never included a `scp`/roles claim, which Microsoft.Identity.Web's `OnTokenValidated` handler (IDW10201) requires even for an otherwise-valid token — undiscovered until the first test requiring a real signed JWT to *succeed* (rather than fail) was written (T079/T090). | Fixed incrementally through Phase 6 (see ledger entries for the "test-isolation gap," "3 InviteAndManageMembersTests failures," and "RevocationWindowTests JWT test-host gap" unplanned fixes). The suite reached 100% green (109/109 unit, 81/81 integration) only at that point — the milestone recorded in the ledger just before Task 91. | No plan/ADR text named these gaps explicitly beforehand; they are recorded here so a future slice building test infrastructure incrementally knows to verify each piece is actually *called*, not just built. |
| 5 | Early in Phase 3: `spec.md` Assumption 5 / FR-017 require three roles (Administrator, Member, Reader); the domain model as first implemented (T014) only had two. Separately, the `IdempotencyRecord` schema as first modeled did not match `data-model.md` (missing fields; `TenantId` needed to be a non-null sentinel rather than nullable, since SQL Server's composite primary key forces `NOT NULL` at the storage level regardless of the CLR nullable type). | Both self-corrected within Phase 3 (task-53b for the role gap; task-55b + T056 Part 0 for the idempotency-record schema, including the sentinel-`TenantId` fix). | Already fully documented in the ledger's own entries for those tasks; flagged by T097's brief as worth a mention here for completeness, since both are genuine "plan/data-model was wrong" findings, not merely code bugs. |
| 6 | `contracts/openapi.yaml`'s `Member` response schema listed `displayName` in its `required` array, but `Domain.Users.User` has no `DisplayName` property anywhere in the domain model (found at T076, carried through T078/T079/T090), so the field was never populated — the contract promised a field the implementation could never honor, a contract-violates-itself defect. | Corrected during the final whole-branch review's fix wave: `displayName` removed from `Member`'s `required` list; the property definition itself is kept (now explicitly `nullable: true` with a note that it is reserved for future use and not currently populated), since the schema may still legitimately document an as-yet-unpopulated optional field. | **Resolved** for the contract-self-consistency defect (the contract no longer promises a field it can't deliver). A **smaller, separately-tracked gap remains open**: `displayName` still isn't populated by the API — this is now correctly an optional field simply never being returned, not a broken promise. Populating it still needs either a domain-model addition (a `DisplayName` or similar property on `User`, populated at JIT-provisioning time from the token's claims) in a future task/slice. |

## Prerequisites Before Implementation

1. ✅ **[ADR-017](../../docs/adr/ADR-017-tenant-context-resolution.md) Accepted** — approved
   by the project owner 2026-08-09.
2. ✅ **`security` skill amended** to distinguish a validated *selector* from a trusted
   *grant*, so its wording no longer contradicts the design FR-010 requires.
3. ✅ **SC-003 scoping decided** — deferred to S7 (above).
4. ⬜ Entra app registrations created per [quickstart.md](quickstart.md) §1. **The one
   remaining blocker**, and it needs a human with app-registration rights in an Entra tenant.

## Next Steps

`/speckit.tasks` to generate the dependency-ordered task list. Suggested ordering, driven by
the risk each phase retires rather than by layer:

1. Solution skeleton, `Directory.Build.props`, central package management, `.editorconfig`
2. Domain — entities, value objects, invariants, with unit tests **written first**
3. Persistence — DbContext, per-entity configurations, named tenant filter, interceptor,
   initial migration
4. **Isolation test harness before any endpoint.** Two tenants seeded, a cross-tenant read
   attempted, and the test **watched failing first** (`idea.md` §59.2, ADR-013 Compliance).
   A green isolation test that was never red proves nothing — and this is the slice where
   that shortcut would be most tempting and most costly.
5. Auth + tenant context resolution middleware (the single ADR-017 seam)
6. Endpoints, story by story: Story 1 (P1) → Story 2 (P2) → Story 3 (P2)
7. Idempotency filter, concurrency/ETag handling
8. Requirement-coverage sweep — every FR mapped to a test (SC-006), gitleaks history scan (SC-008)

Step 4 before step 6 is the deliberate ordering choice in this plan: it makes isolation a
precondition of the endpoints rather than an audit performed on them afterwards.
