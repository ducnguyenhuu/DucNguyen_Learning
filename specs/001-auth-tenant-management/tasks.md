---
description: "Task list for spec 001 — Authentication & Tenant Management (roadmap S2)"
---

# Tasks: Authentication & Tenant Management (S2)

**Input**: Design documents from `/specs/001-auth-tenant-management/`
**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) · [data-model.md](data-model.md) · [contracts/openapi.yaml](contracts/openapi.yaml)
**Governing decisions**: [ADR-013](../../docs/adr/ADR-013-multi-tenancy-model.md) · [ADR-017](../../docs/adr/ADR-017-tenant-context-resolution.md) · [ADR-003](../../docs/adr/ADR-003-service-oriented-architecture.md) · [ADR-002](../../docs/adr/ADR-002-dotnet-first.md)
**Revised**: 2026-08-10 after `/speckit.analyze` — 10 tasks added to close a Principle VII violation (7 functional requirements had no test). See [Revision Note](#revision-note).

**Tests: REQUIRED, not optional.** Unlike the template default, tests are mandatory here and
this is not a stylistic choice — spec SC-004 permits **zero** exceptions on isolation tests,
SC-006 requires every functional requirement to have one, and Constitution Principle VII makes
it a release gate. The `testing` skill and `idea.md` §59.2 additionally require each test to be
**watched failing first**.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1 / US2 / US3, mapping to spec.md user stories
- Every task names an exact file path

## Path conventions

Per plan.md's Structure Decision: `src/Tenancy/Tenancy.{Domain,Application,Infrastructure,Api}`
and `tests/Tenancy.{UnitTests,IntegrationTests}`. Dependencies point inward —
`Api → Application → Domain`, `Infrastructure → Domain`.

---

## Revision Note

`/speckit.analyze` found one CRITICAL issue: **7 of 26 functional requirements had no test
task**, violating Constitution Principle VII ("every functional requirement MUST have automated
test coverage") and spec SC-006. Ten tasks were added:

| Finding | Requirement | Added |
|---|---|---|
| F1 | FR-016 — bounded revocation staleness window had **zero** tasks | T069, T077 |
| F2 | FR-004 — no Tier 2 token-validation tests. research.md R4 said Tier 1 is *"structurally blind"* to audience/issuer errors, and the harness was dropped anyway | T041, T047 |
| F3 | T043's red was the **wrong red** — failing on "route not found" does not prove the test can catch a leak | T060 |
| F4 | FR-020 — invitation issuance idempotency untested | T066 |
| F5 | FR-021 — concurrent edits to the *same membership* untested | T084 |
| F6 | FR-022 — error non-disclosure untested | T052 |
| F7 | FR-025 — "no secret, no unnecessary personal data" in logs untested | T053 |
| F8 | FR-010 — a user *operating* in several tenants without blending untested | T049 |
| A1 | Assertion library was an unresolved decision inside a task | Resolved in T008 |

Task IDs were renumbered to stay sequential in execution order. The original list had 87 tasks;
this has 97.

---

## ⚠️ Read this before starting

**The ordering below deviates deliberately from the usual layer-first sequence.** The isolation
test harness sits in Phase 2 (Foundational), *before* any endpoint exists. That is the point:
it makes tenant isolation a **precondition** of the endpoints rather than an audit performed on
them afterwards. Do not reorder it into a later "testing" phase.

**Two tasks carry the slice's central proof, and they are a pair:**

- **T043** writes a cross-tenant read test and runs it with no endpoint, to watch it fail.
- **T060** is the one that actually matters. Once the endpoint works, it **disables the tenant
  filter** and confirms the test fails *because data leaks* — then re-enables it. T043 alone
  only proves the route is missing; T060 proves the test can catch the bug it exists to catch.
  ADR-013 Compliance requires *"an automated test has actually caught an attempted cross-tenant
  read"*, and only T060 delivers that.

**Prerequisite already satisfied**: the Entra app registrations exist. Tenant
`6cedae69-3542-4a29-bf78-0d82986c4474`, API client `959f992d-dd36-4a49-aada-a73ec5c7ee14`,
created by `infrastructure/scripts/create-entra-app-registrations.sh` and verified against a
real token in [fixtures/sample-entra-token-payload.json](fixtures/sample-entra-token-payload.json).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: solution skeleton, compiler strictness, package management

- [ ] T001 Create `global.json` at repository root pinning the .NET 10 SDK feature band with `rollForward: latestFeature`
- [ ] T002 Create solution `DeliveryIntelligence.slnx` at repository root (.NET 10 XML solution format)
- [ ] T003 [P] Create `Directory.Build.props` at repository root — `Nullable=enable`, `TreatWarningsAsErrors=true`, `EnforceCodeStyleInBuild=true`, `ImplicitUsings=enable`, `LangVersion=latest`
- [ ] T004 [P] Create `Directory.Packages.props` at repository root with `ManagePackageVersionsCentrally=true` and versions from research.md: EF Core 10, Microsoft.Identity.Web 4.14.2, Microsoft.AspNetCore.Authentication.JwtBearer 10.0.10, xunit.v3 3.2.2, Microsoft.AspNetCore.Mvc.Testing 10.0.10, Testcontainers.MsSql 4.11.0, Respawn 6.2.1
- [ ] T005 [P] Create `.editorconfig` at repository root — C# formatting, `dotnet_diagnostic` severities, file-scoped namespaces
- [ ] T006 Create the four service projects `src/Tenancy/Tenancy.Domain`, `Tenancy.Application`, `Tenancy.Infrastructure`, `Tenancy.Api` and wire **inward-only** project references (`Api→Application→Domain`, `Infrastructure→Domain`)
- [ ] T007 [P] Create `tests/Tenancy.UnitTests` and `tests/Tenancy.IntegrationTests` as xunit.v3 projects with `<OutputType>Exe</OutputType>` (v3 test projects are executables, not libraries)
- [ ] T008 Pin **AwesomeAssertions 9.5.0** and `AwesomeAssertions.Analyzers` in `Directory.Packages.props` — the MIT-licensed fork of FluentAssertions 7, chosen because FluentAssertions 8+ moved to a commercial licence (research.md R9). It keeps the `.Should()` syntax, so the example in `.agent/skills/testing/SKILL.md` stays valid
- [ ] T009 Verify `Tenancy.Domain.csproj` has **zero** package references beyond the base library, and record how you verified it — this is the FR-024/ADR-003 boundary that S3 will gate automatically

**Checkpoint**: `dotnet build` succeeds with warnings-as-errors on an empty solution.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the domain model, isolation mechanism, auth, and the test harnesses that prove
isolation and token validation. **No user story may begin until this phase is complete.**

### Domain abstractions and value objects

- [ ] T010 [P] Create `ITenantOwned` marker interface in `src/Tenancy/Tenancy.Domain/Abstractions/ITenantOwned.cs` — the interface the global query filter iterates over
- [ ] T011 [P] Create `IClock` and `SystemClock` in `src/Tenancy/Tenancy.Domain/Abstractions/IClock.cs` — no `DateTime.Now` anywhere, or invitation expiry becomes untestable
- [ ] T012 [P] Create `DomainException` in `src/Tenancy/Tenancy.Domain/Abstractions/DomainException.cs`
- [ ] T013 [P] Create strongly-typed IDs `TenantId`, `UserId`, `MembershipId`, `InvitationId` as `readonly record struct` using `Guid.CreateVersion7()` in `src/Tenancy/Tenancy.Domain/Abstractions/Ids.cs` — v7 is time-ordered, so it does not fragment the clustered index the way v4 does
- [ ] T014 [P] Create `Role`, `TenantStatus`, `MembershipStatus`, `InvitationStatus` in `src/Tenancy/Tenancy.Domain/Abstractions/Enums.cs` — to be persisted as strings, never ordinals
- [ ] T015 [P] Create `EmailAddress` value object with lowercase normalisation in `src/Tenancy/Tenancy.Domain/Abstractions/EmailAddress.cs`

### Domain entities — unit tests written and watched failing first

- [ ] T016 [P] Write failing unit tests for the `Tenant` aggregate (creation, rename validation, status) in `tests/Tenancy.UnitTests/Tenants/TenantTests.cs`. **Run them. Confirm they fail before continuing.**
- [ ] T017 Implement the `Tenant` aggregate in `src/Tenancy/Tenancy.Domain/Tenants/Tenant.cs` — `DisplayName` is required and **not globally unique**, plus an owned `TenantSettings`
- [ ] T018 [P] Write failing unit tests for `User` in `tests/Tenancy.UnitTests/Users/UserTests.cs`
- [ ] T019 Implement `User` in `src/Tenancy/Tenancy.Domain/Users/User.cs` — identity is the composite `(EntraTenantId, EntraObjectId)`; `Email` is display and invitation-matching only, **never** an authorization input (research.md R2)
- [ ] T020 [P] Write failing unit tests for `Membership` in `tests/Tenancy.UnitTests/Memberships/MembershipTests.cs`
- [ ] T021 Implement `Membership` in `src/Tenancy/Tenancy.Domain/Memberships/Membership.cs` — implements `ITenantOwned`; soft-removed via `Status` so FR-025 can report who lost access and when
- [ ] T022 [P] Write failing unit tests for `Invitation` covering expiry, accept, revoke, and terminal-state transitions in `tests/Tenancy.UnitTests/Invitations/InvitationTests.cs`
- [ ] T023 Implement `Invitation` in `src/Tenancy/Tenancy.Domain/Invitations/Invitation.cs` — implements `ITenantOwned`; stores **only** the SHA-256 `TokenHash`, never the token, which is a credential

### Persistence and the isolation mechanism

- [ ] T024 Create `TenancyDbContext` in `src/Tenancy/Tenancy.Infrastructure/Persistence/TenancyDbContext.cs` applying the **named** global query filter `"TenantFilter"` by iterating `Model.GetEntityTypes()` over `ITenantOwned`, with the tenant id read as a **member access on the context instance** so EF lifts it to a SQL parameter (data-model.md)
- [ ] T025 [P] Create one `IEntityTypeConfiguration<T>` per entity in `src/Tenancy/Tenancy.Infrastructure/Persistence/Configurations/` — `rowversion` concurrency tokens, enums as strings, and the filtered unique indexes: `(TenantId, UserId) WHERE Status='Active'` and `(TenantId, Email) WHERE Status='Pending'`
- [ ] T026 [P] Create the covering index for ADR-017's per-request membership lookup — `(TenantId, UserId, Status) INCLUDE (Role)` — in the `Membership` configuration. ADR-017 records this as not optional: it sits on the hot path of every tenant-scoped request
- [ ] T027 Create `TenantSaveChangesInterceptor` in `src/Tenancy/Tenancy.Infrastructure/Persistence/Interceptors/TenantSaveChangesInterceptor.cs` — stamps `TenantId` on insert, rejects any modify/delete whose original `TenantId` differs, and makes `TenantId` immutable. Query filters are **read-side only** (efcore#24122), so without this an attached stub entity can write across tenants
- [ ] T028 Register `TenancyDbContext` with `AddDbContext` (scoped) and the interceptor via DI in `src/Tenancy/Tenancy.Api/Program.cs`. **Not** `AddDbContextPool` — pooling makes the context a reused singleton that cannot carry per-request tenant state
- [ ] T029 [P] Create `IdempotencyRecord` entity and configuration with primary key `(TenantId, Endpoint, Key)` in `src/Tenancy/Tenancy.Infrastructure/Persistence/` — the unique key **is** the concurrency control, and scoping by tenant prevents cross-tenant key probing. **Note in the entity's own comment that nothing purges expired rows in S2**: the 24h TTL is honoured on read, but a purge job would need explicit tenant context (the `distributed-systems` skill's most dangerous case) and no background job exists in this slice by design. Rows accumulate; assign purging to a later slice
- [ ] T030 Create the initial migration `InitialTenancy` in `src/Tenancy/Tenancy.Infrastructure/Migrations/`, then **read the generated SQL** (`dotnet ef migrations script`) before committing — a rename can come out as a drop
- [ ] T031 Add Development-only `await db.Database.MigrateAsync()` in `src/Tenancy/Tenancy.Api/Program.cs`, and add `dotnet ef migrations has-pending-model-changes` to the build. `EnsureCreated()` is prohibited — it bypasses migrations and then makes `Migrate()` fail

### Authentication and tenant context resolution

- [ ] T032 Wire Entra authentication with `AddMicrosoftIdentityWebApi` in `src/Tenancy/Tenancy.Api/Program.cs`, setting `MapInboundClaims = false` so claims stay as `oid`/`tid`/`scp`. **Production code and the test auth handler must agree on claim names** — disagreement here is the classic "tests green, production 403" bug
- [ ] T033 Add `AzureAd` configuration to User Secrets — `TenantId=6cedae69-3542-4a29-bf78-0d82986c4474`, `ClientId=959f992d-dd36-4a49-aada-a73ec5c7ee14`. No client secret exists for this app, by design
- [ ] T034 [P] Create `ITenantContext` in `src/Tenancy/Tenancy.Application/Abstractions/ITenantContext.cs` — exposes the resolved `TenantId` and the caller's `Role`, and **fails closed** rather than defaulting when unresolved
- [ ] T035 Create `TenantContextResolutionMiddleware` in `src/Tenancy/Tenancy.Api/Middleware/TenantContextResolutionMiddleware.cs` — the **single** ADR-017 seam. Treats `{tenantId}` as a candidate, validates it against an active membership for the authenticated `(tid, oid)`, and returns **404** when no membership matches. An endpoint that resolves its own tenant context is a defect
- [ ] T036 [P] Create just-in-time `User` provisioning on first authenticated request, keyed on `(EntraTenantId, EntraObjectId)`, in `src/Tenancy/Tenancy.Application/Users/EnsureUserProvisioned.cs`
- [ ] T037 [P] Create the **audited** cross-tenant helper in `src/Tenancy/Tenancy.Infrastructure/Persistence/Audited/MembershipDirectory.cs` — the only code permitted to bypass the tenant filter, by name (`IgnoreQueryFilters(["TenantFilter"])`), with `UserId == caller` non-negotiable. A bare no-argument `IgnoreQueryFilters()` is **prohibited** anywhere in the codebase
- [ ] T038 [P] Create RFC 9457 `ProblemDetails` error handling in `src/Tenancy/Tenancy.Api/ErrorHandling/ProblemDetailsHandler.cs` — no internal detail, no stack traces, no disclosure of another tenant's existence (FR-022)

### Test harnesses — before any endpoint exists

- [ ] T039 Create `SqlServerFixture` in `tests/Tenancy.IntegrationTests/Infrastructure/SqlServerFixture.cs` as an **xUnit v3 assembly fixture**, using `Testcontainers.MsSql` pinned to `mcr.microsoft.com/mssql/server:2022-latest`. **Never `2025-latest`** — 2025 RTM requires AVX, which Rosetta does not implement, and it crashes on Apple Silicon (research.md R5). One container per assembly; per-class would be unusable under emulation
- [ ] T040 [P] Create the **Tier 1** `TestAuthHandler` in `tests/Tenancy.IntegrationTests/Infrastructure/TestAuthHandler.cs` — **header-driven** (`X-Test-Oid`, `X-Test-Tid`) so one host is shared and tests stay parallel-safe. It **must** return `AuthenticateResult.NoResult()` when no `Authorization` header is present; the ASP.NET Core docs' sample succeeds unconditionally, which silently disables every 401 test
- [ ] T041 [P] Create the **Tier 2** real-JWT harness in `tests/Tenancy.IntegrationTests/Infrastructure/SignedTokenHarness.cs` — a test RSA signing key, `JwtBearerOptions.TokenValidationParameters.IssuerSigningKey` overridden, `ConfigurationManager` and `Authority` nulled so no metadata is fetched, plus a token minter using `JsonWebTokenHandler`. **This tier exists because Tier 1 is structurally blind to it**: a fake handler cannot detect a misconfigured audience, issuer, or `MapInboundClaims` mismatch, which is exactly the class of bug that passes tests and 403s in production (research.md R4)
- [ ] T042 Create `ApiFactory` (`WebApplicationFactory<Program>`) plus Respawn reset and a **two-tenant seed helper** in `tests/Tenancy.IntegrationTests/Infrastructure/` — seed tenant A and tenant B with distinct members, the fixture every isolation test builds on
- [ ] T043 **Write the first cross-tenant read test and RUN IT. Watch it fail.** Place it in `tests/Tenancy.IntegrationTests/Isolation/CrossTenantReadRefusedTests.cs`. Record the failure output in the commit message. Note honestly that this first red only proves the route is absent — **T060 is the task that proves the test can catch a real leak**, and the slice is not done without it

**Checkpoint**: the domain model, the isolation mechanism, auth, and both test harnesses exist.
User stories can now begin.

---

## Phase 3: User Story 1 — Establish an isolated tenant (Priority: P1) 🎯 MVP

**Goal**: an organisation can create a tenant, become its first administrator, read and rename
it, and list only the tenants it belongs to — with other tenants entirely invisible.

**Independent test**: sign in as a new user, create a tenant, confirm a unique identifier is
returned and the caller is its administrator. Then, signed in as a member of a different
tenant, confirm that tenant is not listed, not readable by identifier, and not modifiable.

### Tests for User Story 1 — write first, watch fail

- [ ] T044 [P] [US1] Write failing isolation tests for **all four** tenant endpoints in `tests/Tenancy.IntegrationTests/Isolation/TenantEndpointIsolationTests.cs` — each asserts refusal **and** that the response is indistinguishable from a non-existent tenant (SC-004, FR-009)
- [ ] T045 [P] [US1] Write failing scenario tests for US1's five acceptance scenarios in `tests/Tenancy.IntegrationTests/Scenarios/EstablishTenantTests.cs`
- [ ] T046 [P] [US1] Write a failing test asserting **401** for every tenant operation with no `Authorization` header in `tests/Tenancy.IntegrationTests/Scenarios/UnauthenticatedTests.cs` (FR-002)
- [ ] T047 [P] [US1] Write failing **Tier 2 token-validation tests** using T041's harness in `tests/Tenancy.IntegrationTests/Scenarios/TokenValidationTests.cs` — reject an **expired** token, a token with the **wrong audience**, a token from the **wrong issuer**, and one with an **invalid signature**, each with 401 (FR-004). These cannot be written against the Tier 1 handler
- [ ] T048 [P] [US1] Write failing tests for the two ADR-017 exceptions this story owns — `POST /tenants` (no tenant context yet) and `GET /tenants` (spans tenants via the audited helper) — in `tests/Tenancy.IntegrationTests/Isolation/UnscopedOperationTests.cs`. `GET /tenants` must return **only** the caller's tenants
- [ ] T049 [P] [US1] Write a failing **multi-tenant membership** test in `tests/Tenancy.IntegrationTests/Scenarios/MultiTenantMembershipTests.cs` — one user holding active membership in **two** tenants operates against each in turn, and **no response blends data across them** (FR-010). Distinct from T048, which only tests the tenant list
- [ ] T050 [P] [US1] Write failing tests for idempotent `POST /tenants` in `tests/Tenancy.IntegrationTests/Scenarios/IdempotencyTests.cs` — replay returns the **stored status and body verbatim** (a 201 replays as 201, never 200); same key with a different body returns **422**; in-flight returns **409**
- [ ] T051 [P] [US1] Write failing concurrency tests for `PATCH /tenants/{tenantId}` in `tests/Tenancy.IntegrationTests/Scenarios/ConcurrencyTests.cs` — missing `If-Match` → **428**, stale → **412**, race at save → **409** (FR-021)
- [ ] T052 [P] [US1] Write failing **error non-disclosure** tests in `tests/Tenancy.IntegrationTests/Scenarios/ErrorDisclosureTests.cs` — assert no response body contains a stack trace, an exception type name, a connection string fragment, a SQL statement, or any other tenant's identifier or display name (FR-022)
- [ ] T053 [P] [US1] Write a failing **log hygiene** test in `tests/Tenancy.IntegrationTests/Scenarios/LogHygieneTests.cs` — capture the log sink across an authenticated request and assert it contains no bearer token, no `Authorization` header value, no secret, and no personal data beyond what the operation requires (FR-025)

### Implementation for User Story 1

- [ ] T054 [US1] Implement the create-tenant use case in `src/Tenancy/Tenancy.Application/Tenants/CreateTenant.cs` — creates the `Tenant` and the creator's `Administrator` `Membership` **in one transaction** (FR-005)
- [ ] T055 [P] [US1] Implement read, rename, and list use cases in `src/Tenancy/Tenancy.Application/Tenants/` — list goes through the audited `MembershipDirectory` from T037
- [ ] T056 [US1] Implement the idempotency endpoint filter in `src/Tenancy/Tenancy.Api/Idempotency/IdempotencyFilter.cs` — insert-and-catch-duplicate on the unique key, record committed **in the same transaction as the business write**, TTL 24h, `InFlight` rows older than 60s reclaimable. A filter, not middleware: middleware runs before routing and model binding
- [ ] T057 [P] [US1] Implement ETag/If-Match helpers over `rowversion` in `src/Tenancy/Tenancy.Api/ETags/` — base64 `rowversion` out, `If-Match` in
- [ ] T058 [US1] Implement the four tenant endpoints in `src/Tenancy/Tenancy.Api/Endpoints/TenantEndpoints.cs` per contracts/openapi.yaml — `POST /tenants`, `GET /tenants`, `GET /tenants/{tenantId}`, `PATCH /tenants/{tenantId}`
- [ ] T059 [P] [US1] Add structured logging for authentication outcomes, tenant mutations, and authorization refusals in `src/Tenancy/Tenancy.Api/` — with **no secret and no unnecessary personal data** (FR-025). Correlated tracing and the audit store are S4
- [ ] T060 **[US1] Prove the isolation test can actually catch a leak.** With the endpoints working and tests green, **temporarily remove the `"TenantFilter"` registration** in `TenancyDbContext`, run the isolation suite, and confirm T043 and T044 fail *because tenant B's data was returned* — not because a route was missing. Restore the filter and confirm green again. **Record both outputs in the commit message.** This is what ADR-013 Compliance means by an automated test having *actually caught* an attempted cross-tenant read; without it, roadmap S2's *Done when* is not satisfied even with a green suite
- [x] T061 [US1] Run the full suite and confirm every US1 test passes — and that each passed by the implementation being correct, not by a test being weakened

**Checkpoint**: US1 is independently functional. Tenants can be created and are mutually
invisible, and the isolation test has been proven capable of catching a leak. This is the MVP —
stop and validate before continuing.

---

## Phase 4: User Story 2 — Invite and manage tenant members (Priority: P2)

**Goal**: an administrator invites colleagues by email, the invited person accepts by
authenticating as that address, and the administrator can list and remove members.

**Independent test**: invite an address, confirm it is pending, accept it as that person,
confirm they are an active member who can read tenant data, then remove them and confirm
access is gone.

### Tests for User Story 2 — write first, watch fail

- [ ] T062 [P] [US2] Write failing isolation tests for every invitation and membership endpoint in `tests/Tenancy.IntegrationTests/Isolation/MembershipEndpointIsolationTests.cs` (SC-004 — zero exceptions)
- [ ] T063 [P] [US2] Write failing scenario tests for US2's six acceptance scenarios in `tests/Tenancy.IntegrationTests/Scenarios/InviteAndManageMembersTests.cs`
- [ ] T064 [P] [US2] Write failing tests for the third ADR-017 exception — `POST /invitations/{token}/accept`, where the caller has no membership yet — in `tests/Tenancy.IntegrationTests/Isolation/UnscopedOperationTests.cs`. Authorization is the token **plus** an identity match; an invitation issued to one address must not be acceptable by another (FR-013)
- [ ] T065 [P] [US2] Write failing tests asserting **404** for unknown, expired, revoked, and already-accepted tokens alike, so token validity cannot be probed, in `tests/Tenancy.IntegrationTests/Scenarios/InvitationRefusalTests.cs`
- [ ] T066 [P] [US2] Write failing **invitation idempotency** tests in `tests/Tenancy.IntegrationTests/Scenarios/InvitationIdempotencyTests.cs` — FR-020 names tenant creation **and invitation issuance**; a duplicated `POST /tenants/{tenantId}/invitations` with the same `Idempotency-Key` must not create two invitations, and must replay the stored 201 verbatim
- [ ] T067 [P] [US2] Write a failing test for the **last-administrator** invariant in `tests/Tenancy.UnitTests/Memberships/LastAdministratorTests.cs` — removal or demotion of the sole administrator must be refused (FR-015)
- [ ] T068 [US2] Write a failing **concurrent-removal** integration test in `tests/Tenancy.IntegrationTests/Scenarios/ConcurrentAdminRemovalTests.cs` — two administrators removing *different* administrators simultaneously when exactly two exist. data-model.md records this as a genuine gap: under `READ COMMITTED` both can observe a count of 2 and both succeed, leaving zero. **A unit test cannot demonstrate this**
- [ ] T069 [P] [US2] Write a failing **revocation staleness** test in `tests/Tenancy.IntegrationTests/Scenarios/RevocationWindowTests.cs` — after a member is removed, a **newly issued** context is refused immediately, while an already-issued token remains cryptographically valid until it expires. Asserts the documented behaviour of FR-016 and Assumption 7 rather than pretending revocation is instantaneous

### Implementation for User Story 2

- [ ] T070 [P] [US2] Implement invitation token generation in `src/Tenancy/Tenancy.Application/Invitations/InvitationToken.cs` — cryptographically random, returned **once** at creation, persisted only as SHA-256
- [ ] T071 [US2] Implement the invite use case in `src/Tenancy/Tenancy.Application/Invitations/InviteMember.cs` — 7-day expiry (Assumption 6), **409** if the address is already an active member or already has a pending invitation
- [ ] T072 [US2] Implement the accept use case in `src/Tenancy/Tenancy.Application/Invitations/AcceptInvitation.cs` — verifies expiry against the injected clock, matches the authenticated identity's email, creates the `Membership`, and makes the invitation terminal
- [ ] T073 [P] [US2] Implement list and revoke use cases in `src/Tenancy/Tenancy.Application/Invitations/`
- [ ] T074 [US2] Implement the last-administrator guard in `src/Tenancy/Tenancy.Domain/Tenants/TenantAdministration.cs` — the domain operation refusing removal or demotion of the sole administrator
- [ ] T075 [US2] Implement the transactional protection T068's test demands — count administrators and write the membership change in **one** transaction at `SERIALIZABLE`, or take the tenant row lock before counting. **Pick one and record which in the commit message**; data-model.md presents both and T068's test is what decides it
- [ ] T076 [P] [US2] Implement list-members and remove-member use cases in `src/Tenancy/Tenancy.Application/Members/`
- [ ] T077 [US2] **Make the FR-016 staleness window explicit rather than implicit.** Surface the expected access-token lifetime as named configuration in `src/Tenancy/Tenancy.Api/appsettings.json` (documented, not secret), assert at startup that it does not exceed one hour, and state the trade-off in a comment: a removed member retains access until their existing token expires (Assumption 7). A security trade-off that lives only in a spec assumption is one nobody will find later
- [ ] T078 [US2] Implement the invitation endpoints in `src/Tenancy/Tenancy.Api/Endpoints/InvitationEndpoints.cs` — including `POST /invitations/{token}/accept`, which is **not** tenant-scoped
- [ ] T079 [US2] Implement the member endpoints in `src/Tenancy/Tenancy.Api/Endpoints/MemberEndpoints.cs` — `GET` and `DELETE` on members
- [ ] T080 [P] [US2] Implement a development-time invitation delivery sink (logged or captured locally) in `src/Tenancy/Tenancy.Infrastructure/Notifications/` — Assumption 8 requires only that a pending invitation is recorded and acceptable

**Checkpoint**: US1 and US2 both work independently. A tenant is now collaborative.

---

## Phase 5: User Story 3 — Enforce role-based permissions (Priority: P2)

**Goal**: a member's role determines which operations they may perform — Reader views,
Member acts, Administrator additionally manages settings and membership.

**Independent test**: for each role, attempt each tenant operation and confirm the outcome
matches the permission matrix — permitted operations succeed, forbidden ones are refused as
unauthorised rather than failing obscurely.

### Tests for User Story 3 — write first, watch fail

- [ ] T081 [P] [US3] Write a failing **permission matrix** test in `tests/Tenancy.IntegrationTests/Scenarios/RolePermissionMatrixTests.cs` — every role against every tenant-scoped operation, covering US3's four acceptance scenarios
- [ ] T082 [P] [US3] Write failing tests asserting the **403-versus-404 distinction** in `tests/Tenancy.IntegrationTests/Isolation/ForbiddenVersusNotFoundTests.cs` — an active member with the wrong role gets **403**; a non-member gets **404**. Getting this backwards makes every tenant enumerable by identifier substitution, which is the single most important assertion in the slice
- [ ] T083 [P] [US3] Write failing tests for role change in `tests/Tenancy.IntegrationTests/Scenarios/ChangeMemberRoleTests.cs` — including refusal when it would demote the last administrator
- [ ] T084 [P] [US3] Write a failing **concurrent membership edit** test in `tests/Tenancy.IntegrationTests/Scenarios/ConcurrentRoleEditTests.cs` — two administrators changing the role of the **same** member simultaneously must produce one success and one **409**, with no lost update. This is the spec's own edge case, and it is distinct from T068's last-administrator race (FR-021)

### Implementation for User Story 3

- [ ] T085 [US3] Implement role-based authorization requirements and handlers in `src/Tenancy/Tenancy.Api/Authorization/` — evaluated against the **membership resolved in T035**, never against a token claim (ADR-017 step 5)
- [ ] T086 [P] [US3] Implement the change-role use case in `src/Tenancy/Tenancy.Application/Members/ChangeMemberRole.cs`, reusing T074's last-administrator guard and honouring the `rowversion` concurrency token
- [ ] T087 [US3] Implement `PATCH /tenants/{tenantId}/members/{userId}` in `src/Tenancy/Tenancy.Api/Endpoints/MemberEndpoints.cs`
- [ ] T088 [US3] Apply the authorization policies across every endpoint from US1 and US2 per contracts/openapi.yaml — administrator-only on tenant settings and all membership management (FR-019)

**Checkpoint**: all three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T089 Build the **FR coverage matrix** in `specs/001-auth-tenant-management/coverage.md` — map all 26 functional requirements to the tests covering them (SC-006). `/speckit.analyze` found 7 with no test on the first pass; this matrix is what makes a recurrence visible. Any FR still without a test is either a missing test or a badly written requirement — resolve it rather than recording the gap
- [ ] T090 Confirm all **15 acceptance scenarios** from spec.md pass, and tick roadmap S2's *Done when* list item by item
- [ ] T091 Measure the full suite runtime and confirm it is **under 5 minutes** unattended (SC-006). Record the number as the baseline S3 must hold
- [ ] T092 [P] Run `gitleaks detect --no-git=false` and confirm **no secret anywhere in git history**, not just the working tree (SC-008, roadmap S2). A secret committed once is compromised even after removal
- [ ] T093 [P] Walk [quickstart.md](quickstart.md) end to end on a clean checkout against an **empty** database, confirming migrations apply and the app serves requests with no manual step (SC-007)
- [ ] T094 [P] Record the real timing for SC-001 and SC-002 along the API path, and note explicitly that the *"without documentation"* clause stays **unverified** until a UI exists (plan.md Complexity Tracking)
- [ ] T095 Audit for the research.md R3 bypass list — confirm **no** `Find`/`FindAsync` on tenant-scoped entities, **no** bare `IgnoreQueryFilters()`, **no** raw SQL, and **no** `ExecuteUpdate`/`ExecuteDelete`. Write down what you found; S3 turns this manual audit into a build gate
- [ ] T096 [P] Confirm every background-job-shaped code path either does not exist or establishes tenant context explicitly — the likeliest cross-tenant leak route under ADR-013, currently unguarded (traceability U12, assigned to S3)
- [x] T097 Note anything in the plan, research, or ADRs that proved wrong during implementation, in `specs/001-auth-tenant-management/plan.md` or a new ADR (SC-009). Silently working around a recorded decision is prohibited (Principle II)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 Setup** — no dependencies
- **Phase 2 Foundational** — depends on Phase 1. **Blocks all user stories**
- **Phase 3 US1 (P1)** — depends on Phase 2. This is the MVP, and it contains T060, the task that proves the isolation test works
- **Phase 4 US2 (P2)** — depends on Phase 2. Uses `Membership` from Phase 2 and the tenant from US1 in practice, though independently testable by seeding
- **Phase 5 US3 (P2)** — depends on Phase 2. Enforces authorization across endpoints delivered by US1 and US2, so in practice run it after both
- **Phase 6 Polish** — depends on all three stories

### Within each user story

Tests written and **watched failing** → domain → application → endpoints → integration.

### Critical path

```
T001..T009  Setup
        ↓
T010..T023  Domain (unit tests first)
        ↓
T024..T031  Persistence + named tenant filter + interceptor
        ↓
T032..T038  Auth + ADR-017 resolution seam + audited helper
        ↓
T039..T043  Harnesses (Tier 1 + Tier 2) → first red isolation test
        ↓
T044..T059  US1 tests then implementation
        ↓
T060        ★ PROVE THE ISOLATION TEST CATCHES A LEAK  ← the real gate
        ↓
T061        US1 green
        ↓
T062..T080  US2        T081..T088  US3
        ↓
T089..T097  Polish
```

### Parallel opportunities

- T003, T004, T005 — root config files, independent
- T010–T015 — domain abstractions, all different files
- T016, T018, T020, T022 — the four entity unit-test files, written together before their implementations
- T025, T026, T029 — EF configurations in separate files
- T040, T041 — the two auth harnesses, independent of each other
- T044–T053 — all ten US1 test files
- T062–T067, T069 — US2 test files (T068 is sequential: it needs the seed helper's two-admin state)
- T081–T084 — all US3 test files
- T092, T093, T094, T096 — independent polish checks

**Not parallelisable despite appearances**: T024 (DbContext) and T027 (interceptor) both define
the isolation mechanism and must be reasoned about together. **T060 is a hard sequential gate** —
it deliberately breaks the build's correctness for one run, so nothing else may be in flight.

---

## Parallel Example: User Story 1 tests

```bash
# Write all ten US1 test files together, then run them and confirm they all fail:
Task: "T044 Isolation tests for four tenant endpoints"
Task: "T045 Scenario tests for US1's five acceptance scenarios"
Task: "T046 401 tests (FR-002)"
Task: "T047 Tier 2 token-validation tests — expired / wrong audience / wrong issuer / bad signature (FR-004)"
Task: "T048 ADR-017 unscoped-operation tests"
Task: "T049 Multi-tenant membership, no blending (FR-010)"
Task: "T050 Idempotency tests (FR-020)"
Task: "T051 Concurrency/ETag tests (FR-021)"
Task: "T052 Error non-disclosure tests (FR-022)"
Task: "T053 Log hygiene tests (FR-025)"

dotnet test   # expect ALL to fail. That is the point.
```

---

## Implementation Strategy

### MVP first

1. Phase 1 Setup
2. Phase 2 Foundational — **critical**, and do not shortcut T043
3. Phase 3 US1, including **T060**
4. **Stop and validate**: two tenants exist and are mutually invisible, proven by a test that
   has been observed failing *for the right reason*
5. This is a demonstrable slice on its own: it proves safe multi-customer onboarding

### Incremental delivery

US1 → collaborative tenants (US2) → enforced permissions (US3) → polish. Each increment adds
value without breaking the previous one.

### Solo-developer note

The "parallel team strategy" in the template does not apply here — this is a one-person
project. Read `[P]` as *"these can be done in any order without stepping on each other"*,
which is still useful for batching similar work, not as *"run these simultaneously"*.

---

## Notes

- `[P]` = different files, no dependency on incomplete work
- `[Story]` maps each task to a spec.md user story for traceability
- **Verify every test fails before implementing it**, and for isolation specifically, verify it
  fails *for the right reason* (T060). ADR-013's Compliance section and roadmap S2's *Done when*
  both require an isolation test that demonstrably could have failed
- Commit after each task or logical group, Conventional Commits per CLAUDE.md
- **Do not weaken a test to make it pass.** If an isolation test is hard to satisfy, the design
  is wrong, not the test
- Tasks are guidance, not a blind checklist (`idea.md` §35, Principle II) — inspect the existing
  code and check the relevant ADR before each one
