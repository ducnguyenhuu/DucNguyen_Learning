# FR Coverage Matrix (T089, SC-006)

Maps all 26 functional requirements in [spec.md](spec.md) to the tests that exercise them. Built
by reading every test file under `tests/Tenancy.UnitTests/` and `tests/Tenancy.IntegrationTests/`
and verifying each citation against the actual test body, not just a doc-comment mention of an
FR number. Full methodology, gap-closure detail, and verification output:
`.superpowers/sdd/tasks/task-89-report.md`.

**Provenance note**: this task's brief states `/speckit.analyze`'s first pass found 7 FRs with no
test. No artifact in this repository (git log, `progress.md`, or any `.superpowers/sdd` file)
records which 7 — that could not be reconstructed and is stated here plainly rather than guessed.
What follows is an independent, from-scratch survey; three FRs (FR-023, FR-024, FR-025's
authz-refusal-logging path is unclosed, FR-026's mechanism-existence half) had zero test before
this task and were closed by new tests, listed at the bottom.

| FR | Requirement (short paraphrase) | Covering test(s) | Notes |
|---|---|---|---|
| FR-001 | Auth via corporate IdP only; no password storage/management | `Tenancy.IntegrationTests/Scenarios/TokenValidationTests.cs`: 4 tests (expired/wrong-audience/wrong-issuer/invalid-signature) | No password field exists anywhere in the domain to test the negative of; coverage is by construction (every auth path is JWT-only). |
| FR-002 | Reject unauthenticated requests to non-public endpoints; disclose nothing | `Scenarios/UnauthenticatedTests.cs` (4 tests); `Scenarios/EstablishTenantTests.Get_Tenants_WithoutAuthentication_IsRejectedAsUnauthenticated` | Solid. |
| FR-003 | Resolve caller to a stable identity across sessions | `Tenancy.UnitTests/Users/UserTests.cs.Create_TwoUsersWithSameEntraIdentityButDifferentEmail_ExposeSameComparableEntraIdentity` | Domain-level proof; every scenario re-authenticating the same seeded identity across requests implicitly reinforces it. |
| FR-004 | Reject expired/malformed/wrong-audience/wrong-issuer credentials | `TokenValidationTests` (4 tests) | Solid. |
| FR-005 | Authenticated user creates tenant; unique id; creator = first admin | `UnitTests/Tenants/CreateTenantTests.ExecuteAsync_CreatesTenantAndAdministratorMembership_InOneCall`; `Scenarios/EstablishTenantTests.Post_Tenants_WithValidDisplayName_CreatesTenant_AndReturnsItToCaller`; `Isolation/UnscopedOperationTests.Post_Tenants_WithoutAnyTenantContext_Succeeds` | Solid. |
| FR-006 | Admin reads/updates tenant display name & settings | `UnitTests/Tenants/GetRenameListTenantsTests` (2 tests); `Scenarios/EstablishTenantTests.Patch_TenantDisplayName_ThenGet_ReflectsUpdatedName`; `Scenarios/RolePermissionMatrixTests.Get_TenantDetails_AsMember_Succeeds` | Display name fully covered; "settings" has no separately-modifiable field yet in the domain model beyond display name. |
| FR-007 | Resolve to exactly one active tenant context; reject absent/malformed/non-member | `Isolation/TenantEndpointIsolationTests` (2 tests); `Isolation/CrossTenantReadRefusedTests`; `Scenarios/ErrorDisclosureTests.Get_TenantById_WithMalformedRouteId_DoesNotDiscloseSensitiveDetail`; `Scenarios/UnauthenticatedTests` | Solid, multi-angle. |
| FR-008 | Prevent all cross-tenant data access | `Isolation/TenantEndpointIsolationTests`, `Isolation/CrossTenantReadRefusedTests`, `Isolation/MembershipEndpointIsolationTests` (5), `Isolation/ForbiddenVersusNotFoundTests` (3), `Scenarios/MultiTenantMembershipTests.Get_TenantById_ForEachTenant_ReturnsThatTenantsOwnData_NeverBlended` | The most heavily-tested FR in the suite (includes T060's live leak-reproduction proof). |
| FR-009 | Inaccessible tenant indistinguishable from nonexistent | `Isolation/TenantEndpointIsolationTests` (byte-for-byte body comparison); `Isolation/ForbiddenVersusNotFoundTests` (2); `Scenarios/RevocationWindowTests.RemovedMember_FreshRequest_IsRefused_AndIndistinguishableFromNeverAMember` | Solid. |
| FR-010 | One user, many tenants, no blending within a tenant-scoped response | `Scenarios/MultiTenantMembershipTests` (2 tests); `UnitTests/Tenants/GetRenameListTenantsTests.ListTenants_CallsGetManyByIdsAsync_WithDistinctTenantIdsFromMemberships` | Solid; also exercises FR-010's K2 clarification exempting the tenant-list operation itself. |
| FR-011 | Admin invites by email+role; pending with expiry | `UnitTests/Invitations/InviteMemberTests.ExecuteAsync_HappyPath_CreatesPendingInvitationWithSevenDayExpiry_AndReturnsRawTokenOnce`; `Scenarios/InviteAndManageMembersTests.Post_Invitation_WithEmailAndRole_RecordsPendingInvitation`; `Scenarios/RolePermissionMatrixTests.Post_Invitation_AsAdministrator_Succeeds` | Solid. |
| FR-012 | Invited person, authenticated as invited email, accepts and becomes active member with invited role | `UnitTests/Invitations/AcceptInvitationTests.ExecuteAsync_HappyPath_...`; `Scenarios/InviteAndManageMembersTests.Post_Invitation_ThenAccept_ThenListMembers_ShowsNewActiveMemberWithInvitedRole`*; `Isolation/UnscopedOperationTests.Post_AcceptInvitation_AsInvitedAddressee_Succeeds`* | Proven unconditionally at unit level. *Both starred integration tests are currently in the documented pre-existing-failure set (test-isolation flakiness, see progress.md T078-80) — not a code defect. |
| FR-013 | Refuse expired/accepted/revoked/wrong-identity invitation acceptance | `AcceptInvitationTests` (4 tests, one per category); `Scenarios/InvitationRefusalTests` (4 tests); `Scenarios/InviteAndManageMembersTests.Post_AcceptInvitation_AsDifferentEmailThanInvited_IsRefused`; `Isolation/UnscopedOperationTests.Post_AcceptInvitation_WithValidTokenForSomeoneElse_IsRefused` | Exhaustive, unit + integration. |
| FR-014 | Admin lists members/invitations, revokes invitation, removes member, changes role | `UnitTests/Members/ListMembersTests`, `Invitations/ListInvitationsTests`, `Invitations/RevokeInvitationTests`, `Members/RemoveMemberTests`, `Members/ChangeMemberRoleTests`; `Scenarios/ChangeMemberRoleTests` (5) | Solid, exhaustive. |
| FR-015 | Every tenant retains ≥1 admin; refuse violating removal/demotion | `UnitTests/Memberships/LastAdministratorTests` (5); `Members/RemoveMemberTests.ExecuteAsync_LastAdministrator_ReturnsConflict`; `Members/ChangeMemberRoleTests.ExecuteAsync_LastAdministrator_ReturnsConflict_AndNeverSaves`; `Scenarios/InviteAndManageMembersTests.Delete_SoleAdministrator_IsRefused`*; `Scenarios/ChangeMemberRoleTests.Patch_MemberRole_SoleAdministratorDemotesSelf_IsRefused`; `Scenarios/ConcurrentAdminRemovalTests...`; `Scenarios/ConcurrentAdminRemovalRepositoryTests...` | Exceptional coverage across unit/integration/genuine-concurrency. *Starred test is in the pre-existing-failure set. |
| FR-016 | Revoke removed member's access within a bounded, documented staleness window | `UnitTests/Configuration/TokenLifetimeValidationTests`; `Scenarios/RevocationWindowTests.RemovedMember_FreshRequest_IsRefused_AndIndistinguishableFromNeverAMember`; `.AlreadyIssuedToken_ReplayedAfterRemoval_IsNotRejectedOnTokenGrounds`* | Both halves of Assumption 7's trade-off are modeled. *Second half's proof test is in the pre-existing-failure set for an unrelated test-host JWT-signing wiring gap, not the property itself. |
| FR-017 | Each membership exactly one role from {Administrator, Member, Reader} | `UnitTests/Memberships/MembershipTests.Create_WithGivenRole_ExposesThatRole` (Theory); `Authorization/AdministratorOnlyAuthorizationHandlerTests` (Theory) | Role set/assignment tested for all three roles. Member-vs-Reader *behavioral* distinction is **explicitly untestable in S2 per spec.md's Assumption 5 (K3)** — a spec-acknowledged exception, not a gap. |
| FR-018 | Evaluate every tenant-scoped op against caller's role; refuse as Forbidden, distinct from Unauthenticated | `Authorization/AdministratorOnlyAuthorizationHandlerTests`; `Scenarios/RolePermissionMatrixTests` (6); `Isolation/ForbiddenVersusNotFoundTests.Post_Invitation_AsWrongRoleMember_Returns403` | Solid; explicitly distinguishes 403/401/404. |
| FR-019 | Restrict tenant-settings changes & all membership management to admins | `Scenarios/RolePermissionMatrixTests` (6); `Authorization/AdministratorOnlyAuthorizationHandlerTests` | Solid, exhaustive; same Member/Reader caveat as FR-017/018. |
| FR-020 | Idempotent tenant creation & invitation issuance | `Scenarios/IdempotencyTests` (3); `Scenarios/InvitationIdempotencyTests` (2) | Solid. |
| FR-021 | Prevent lost updates on concurrent tenant/membership changes | `Scenarios/ConcurrencyTests` (incl. the `RenameWithOriginalRowVersionAsync` EF no-op-skip regression test); `Scenarios/ConcurrentRoleEditTests.Patch_MemberRole_TwoAdministrators_SameIfMatch_Concurrently_ExactlyOneWinsWithNoLostUpdate`; `Scenarios/ChangeMemberRoleTests` (428/400/412) | Very well covered, includes real-concurrency ground-truth verification. |
| FR-022 | Errors identify the problem without disclosing internal detail or other tenants' existence | `Scenarios/ErrorDisclosureTests` (3) | Solid, dedicated file. |
| FR-023 | Tenancy capability owns its data exclusively; only its published interface may read/write it | **New**: `Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.OnlyTenancyApi_ReferencesInfrastructureDirectly`, `.NoCapabilityOtherThanTenancyExistsUnderSrc` | **Gap found and closed** (T089). Zero test before this task. No second capability exists yet to violate the boundary against; closed with the strongest available structural proof (only `Tenancy.Api` references `Tenancy.Infrastructure` directly) plus an explicit pin that no second capability exists, so a future one is a visible decision. |
| FR-024 | Domain layer MUST NOT depend on infrastructure | **New**: `CapabilityBoundaryTests.TenancyDomain_HasNoProjectReferences`, `.TenancyApplication_OnlyReferencesDomain`, `.TenancyInfrastructure_NeverReferencedByDomainOrApplication` | **Gap found and closed** (T089). Automated *general* architecture-boundary enforcement remains correctly deferred to S3 (`old-FR-028`); these new tests assert the actual `.csproj` dependency graph today, closing the gap now rather than waiting for S3's dedicated tooling. |
| FR-025 | Log every auth outcome, tenant mutation, membership change, and authz refusal with structured detail; no secrets/unnecessary PII | **New**: `Tenancy.IntegrationTests/Scenarios/LoggingCoverageTests` (4 tests — tenant creation, membership-resolution-failure, member removal, role-based authorization refusal). `Tenancy.UnitTests/Authorization/AdministratorOnlyAuthorizationHandlerTests` (2 new tests covering the same refusal log call at the unit level, plus a regression guard that the success path logs nothing). Existing: `Scenarios/LogHygieneTests.AuthenticatedRequest_NeverLogsBearerTokenOrSecretHeaderValues` | **Gap found and fully closed.** The pre-existing `LogHygieneTests` test explicitly disclaims covering the substantive requirement. All 4 categories now have real structured logging proven, without unnecessary PII. The previously-missing 4th category (role-based authorization-forbidden logging) now has a production `ILogger<AdministratorOnlyAuthorizationHandler>.LogWarning("Authorization refused: tenant {TenantId}, user {UserId}, required role {RequiredRole}, actual role {ActualRole}", ...)` call in `AdministratorOnlyAuthorizationHandler.HandleRequirementAsync` (T085) — placed there, not in `RequireTenantAdministratorFilter` (T088), because the handler is the only place with both the tenant context and the caller's actual resolved role; the filter only ever sees a bare `AuthorizationResult.Succeeded == false`. |
| FR-026 | No secret/credential/connection-string in source control; local secrets excluded via a real mechanism | **New**: `Tenancy.UnitTests/Architecture/SecretExclusionTests` (9 test cases: `.gitignore` patterns, `UserSecretsId` wiring, no embedded connection-string credential) | **Gap found and partially closed** (T089). No automated test existed; only a manual, unchecked task-list item (T092, `gitleaks`). New tests prove the mechanism itself is real and structurally correct. Full-history secret scanning (manual, T092) and a CI enforcement gate (no `.github/workflows/` exists in this repo; CI/CD is explicitly S7 per spec.md's Non-Goals) remain open and are not claimed as closed. |

## Gaps found and closed by this task

FR-023, FR-024, FR-025 (partial), FR-026 (partial) had zero covering test before this task and are
not spec-acknowledged exceptions. New tests were written to close them:

- `tests/Tenancy.UnitTests/Architecture/CapabilityBoundaryTests.cs` — FR-023, FR-024
- `tests/Tenancy.UnitTests/Architecture/SecretExclusionTests.cs` — FR-026
- `tests/Tenancy.IntegrationTests/Scenarios/LoggingCoverageTests.cs` — FR-025

FR-025's remaining gap (no production log call on the role-based authorization-refusal path) was
closed in a follow-up fix: a `LogWarning` call was added to
`src/Tenancy/Tenancy.Api/Authorization/AdministratorOnlyAuthorizationHandler.cs`, with covering
tests added to both `LoggingCoverageTests.cs` (integration) and
`tests/Tenancy.UnitTests/Authorization/AdministratorOnlyAuthorizationHandlerTests.cs` (unit). FR-025
is now fully closed, not partial.

The only requirement genuinely left untested by deliberate spec design is the Member-vs-Reader
behavioral distinction inside FR-017/018/019 — explicitly named untestable-in-S2 by spec.md's own
Assumption 5 (K3), which this matrix treats as a documented exception rather than a gap.

Full detail, literal test output, and the exact `dotnet test` verification runs: see
`.superpowers/sdd/tasks/task-89-report.md`.

---

## S3 Runtime Baseline (T091)

**Measurement date**: 2026-08-13
**Baseline commit**: `a9cef78f2469fa6ca63dc0808508b98ee9679d81`
**Requirement**: Full suite runs unattended in under 5 minutes (SC-006)

### Timings (3 runs, macOS arm64)

| Run | Duration | Test Results |
|-----|----------|--------------|
| 1 (cold start) | **18.445s** | 190/190 ✅ |
| 2 (warm cache) | 20.826s | 190/190 ✅ |
| 3 (warm cache) | 21.040s | 190/190 ✅ |

- **Min**: 18.445s
- **Median**: 20.826s
- **Max**: 21.040s
- **Margin vs. 5-min bar**: ✅ ~21s vs 300s (92% under bar)

The suite has ample headroom for growth as new tests are added. Full measurement detail and run output: `.superpowers/sdd/tasks/task-91-report.md`.

---

## T092: gitleaks Secret Detection Scan

**Execution date**: 2026-08-13  
**Operator**: Claude Code  
**Tool**: gitleaks 8.30.1 (Homebrew)  
**Initial scan result**: 1 finding detected

### Finding & Analysis

**Flagged value**: SHA-256 hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85`  
**Location**: `tests/Tenancy.UnitTests/Invitations/InvitationTests.cs`, line 44  
**Rule**: generic-api-key  
**Status**: Confirmed false positive

**Justification**:
- This is the SHA-256 hash of an empty string (well-known, publicly-documented test constant)
- Used as a test fixture constant (`private const string SampleTokenHash`)
- Not a real credential, API key, token, or secret material
- Appropriate and safe for test code

### Resolution Applied

A `.gitleaks.toml` configuration file was created at the repository root with a narrowly-scoped allowlist entry:

```toml
[allowlist]
# SHA-256 hash of an empty string (e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85) used as a test fixture constant in InvitationTests — not a real credential, confirmed false positive
commits = ["0ecc91076efc6c45039441f556e73d075d4119fb"]
paths = ["tests/Tenancy.UnitTests/Invitations/InvitationTests.cs"]
regexes = ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85"]
```

**Scope**: Allowlist is narrowly constrained to the specific commit, file, and exact hash value to prevent over-suppression of future genuine findings elsewhere in the codebase.

### Verification

**Command**: `gitleaks detect --no-git=false --verbose`  
**Result**: ✅ **CLEAN** (0 findings, exit code 0)

```
9:14PM INF 124 commits scanned.
9:14PM INF scanned ~1377465 bytes (1.38 MB) in 293ms
9:14PM INF no leaks found
```

**Status**: COMPLETE — False positive confirmed, allowlisted, and clean scan verified.

For full analysis and decision trail, see `.superpowers/sdd/tasks/task-92-report.md`.
