# ADR-025: One organization per deployment; multi-tenancy removed

**Status**: Accepted
**Date**: 2026-10-23
**Deciders**: Project owner (accepted 2026-10-23)
**Relates to**: Supersedes ADR-013 and ADR-017 · refines ADR-022 (point 4) · ADR-019 · Constitution → Principle IV (retired by amendment 2.0.0), Principle X · `specs/001-auth-tenant-management` · roadmap S2, S7, S8

## Context

ADR-013 made the platform multi-tenant SaaS, and S2 built that in full: a `Tenant` aggregate,
a tenant id on every owned row, a named global query filter, a save interceptor that stamped and
guarded tenant ids, a route-selected tenant context (ADR-017), a cross-tenant isolation test
suite, and tenant enrichment on spans and logs.

That machinery is a large share of the code and of every later slice's cost. S8's messages, S9's
connector credentials, S12's AI cost attribution and Track B's vector indexes would each have to
carry and enforce a tenant boundary. The project is a learning exercise run by one person, with
no customers and no second organization. The owner decided multi-tenancy is not worth that cost.

Nothing is deployed: S6 and S7 are waiting for an Azure subscription. No database holds tenant
data that would need migrating.

## Decision

1. **One deployment serves one organization.** No `Tenant` entity, tenant id, tenant route
   segment, tenant query filter, or tenant save interceptor exists. The organization is implicit;
   it has no name or settings of its own.
2. **Membership stays, without a tenant.** A user has at most one active `Membership`, holding
   one role from Administrator, Member and Reader. Invitations, role changes, removal,
   the last-administrator rule (FR-015), optimistic concurrency, idempotency and the audit log
   all stay. They are scoped to the organization instead of to a tenant.
3. **Caller membership is resolved once per request.** Routes that need a member opt in with
   `RequireMembership()`. The filter looks up the caller's active membership from the token's
   `(tid, oid)` and fills `ICallerContext` (user id and role). An authenticated caller with no
   active membership gets **403**. The 404-masking of ADR-017 is gone, because there is no tenant
   whose existence could be probed. Administrator-only routes add `RequireAdministrator()`, which
   reads the role from `ICallerContext`, never from a token claim.
4. **The first administrator bootstraps.** `POST /members/bootstrap` makes the caller an
   Administrator only while the organization has no active members. Otherwise it returns 409.
   Only a delegated user token (scope `access_as_user`) may call it, never an application
   identity. A transaction-scoped application lock serializes concurrent attempts. This replaces
   `POST /tenants`, so the trust level matches what existed before: any signed-in user could
   create a tenant and become its administrator.
5. **`GET /me` returns the caller's own user id, email and role.** The role is `null` for a
   non-member. This replaces `GET /tenants` as the "what can I do here" call, and it is the
   S7 load-test read path.
6. **The routes are** `GET /me`, `POST /members/bootstrap`, `GET /members`,
   `PATCH|DELETE /members/{userId}`, `POST|GET /invitations`,
   `DELETE /invitations/{invitationId}`, and `POST /invitations/{token}/accept`.
7. **Telemetry carries `user.id` and no tenant attribute.** Audit entries have no tenant column.
   The idempotency key is `(CreatedByUserId, Endpoint, Key)`.
8. **The schema starts again from one migration.** The five migrations from S2 to S4 are replaced
   by a single initial migration. This is safe only because nothing is deployed. A local compose
   volume made before this change must be recreated (`docker compose down -v`).
9. **Entra's own "tenant" stays.** `User` keeps its `(EntraTenantId, EntraObjectId)` identity key,
   and ADR-019 still holds. That key is the identity provider's directory, not application tenancy.
10. **Spec 001 is kept as history, not rewritten.** Its requirements are read this way:
    - **Retired:** FR-006 (tenant name and settings), FR-007 (tenant context), FR-008 (cross-tenant
      access), FR-009 (inaccessible looks like nonexistent), FR-010 (membership in several
      tenants), SC-004 and SC-005.
    - **Reinterpreted:** FR-005 now means "the first authenticated user can bootstrap as the first
      administrator". Every other "tenant" in the spec now means "the organization".
    - **SC-003** becomes: 95% of `GET /me` calls under 1 s at 50 concurrent callers.
    `RequirementCoverageGates` excludes the retired requirements by name, citing this ADR.

## Consequences

### Positive

- The API, persistence layer and test suite get a lot smaller. A whole class of bugs disappears:
  forgotten filters, interceptor stamping, background work without a tenant context.
- Later slices stop paying the tenant cost: S8 messages, S9 credentials, S12 cost attribution,
  and Track B indexes.
- The constitution gets simpler. Principle IV is retired rather than satisfied slice after slice.

### Negative

- **Serving a second organization now means a second deployment**, or reintroducing tenancy
  later. Retrofitting tenancy is far more expensive than keeping it, because every table, query,
  message and index has to change at once. This is the real cost of this decision.
- The project no longer practises one of the hardest SaaS skills `idea.md` set out to learn,
  which is proving tenant isolation under test.
- Bootstrap is first-come within the Entra directory. Between deployment and the owner's first
  sign-in, any user in that directory could claim the first administrator role. This is
  acceptable with one single-owner directory (ADR-019), and it is the same exposure
  `POST /tenants` had.

### Neutral / accepted trade-offs

- The app role value `Tenancy.Automation.Member` and the GitHub variable `TENANCY_API_APP_ID_URI`
  keep their old names. They live in Entra and GitHub, outside this repo, and renaming them
  would break those registrations for no functional gain.
- Specs 001–006 still describe tenants. Each carries a banner pointing here.
- Other Accepted ADRs mention tenants in passing: 001, 002, 003, 008, 009, 011, 018, 020 and 021.
  They are not edited. Read "tenant" there as "the organization", and read "per-tenant
  attribution" (008, 009) as "per-caller attribution".

## Alternatives Considered

### Keep multi-tenancy

This is the most valuable option for a commercial product, and the cost is already paid for S2.
It was rejected on cost going forward: every later slice must carry the boundary, and there is no
second organization to protect.

### Keep a single hard-coded tenant row

Keeping the `Tenant` table and all the isolation machinery but seeding one row would preserve the
option of going multi-tenant later. It was rejected because it keeps all of the complexity while
proving nothing: isolation code that never has two tenants to separate is untested in practice.

### Configured bootstrap administrator (by Entra object id)

This is safer than first-come, and nobody can race the owner. It was rejected for now because it
needs deployment-time configuration in Terraform and in the pipeline for a single-owner directory.
It is the expected fix if the directory ever gains other users. See Revisit When.

### Authentication only, roles from Entra app roles

This would drop memberships and invitations and read roles from the token. It is much smaller,
but it discards most of S2's work and moves authorization data into Entra, where it cannot be
audited or tested locally.

## Revisit When

- A second organization needs to use the platform. Choose between per-organization deployments
  and reintroducing tenancy. Do not quietly add tenant columns.
- The Entra directory gains users other than the owner. Then replace first-come bootstrap with a
  configured bootstrap administrator.

## Compliance

- `RequirementCoverageGates` lists the retired spec 001 requirements explicitly. Removing a
  requirement from coverage needs an entry in that list, and the list cites this ADR.
- `MembershipResolutionTests` (integration) proves every member-only route refuses an
  authenticated non-member with 403. `RolePermissionMatrixTests` proves every
  administrator-only route refuses Member and Reader.
- `RawSqlGates` allow-lists the one application-lock call, with its justification.
- No automated gate stops someone from reintroducing tenant columns. That is a review-time check
  against this ADR.
