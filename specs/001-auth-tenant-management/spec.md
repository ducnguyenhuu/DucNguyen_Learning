# Feature Specification: Authentication & Tenant Management

**Feature Branch**: `001-auth-tenant-management`
**Created**: 2026-08-08
**Narrowed**: 2026-08-08 — scope reduced to slice S2 (see Revision Note)
**Status**: Draft
**Roadmap slice**: **S2** — Auth + Tenant + Persistence (local). See [roadmap.md](../../roadmap.md).
**Input**: First code slice of the AI Engineering & Delivery Intelligence Platform, per `idea.md` §47. Deliberately contains no AI capability.

## Revision Note

This specification originally also covered observability, containerization,
Terraform/Azure provisioning, and CI/CD as a fourth user story. That made it span
roadmap slices S2 through S7 — roughly six slices of work behind one heading, which
is the "large incomplete technical layer" `idea.md` §29 prohibits.

It has been narrowed to **S2 only**. Everything removed is recorded in
[Deferred Requirements](#deferred-requirements) with its target slice, so nothing is
lost. Gate 1 in roadmap.md still requires all of S2–S8 before Horizon 2 begins.

## Context & Intent

This is the platform's first code slice. Its purpose:

1. **Product value**: an organisation can establish an isolated tenant, invite
   colleagues, and control who may do what inside it. Nothing else in the product
   can be built or sold until this exists, because tenancy is the root of the data
   model and the security model.
2. **Architectural proof, in part**: it establishes the domain model, clean
   architecture layering, identity integration, and tenant-isolated persistence.
   The remainder of the end-to-end path — telemetry, containers, Azure, pipeline —
   is proven in S3–S7.

This slice is complete when it is verifiable **on a development machine**. Azure
deployment is explicitly not part of it.

**Explicitly out of scope**: projects, teams, releases, risks, integrations with
external systems, any AI or intelligence capability, any analytics or reporting.
Those arrive in later horizons and must not be anticipated here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Establish an isolated tenant (Priority: P1)

A person from a software organisation signs in with their existing corporate identity and creates a tenant representing their organisation. They become that tenant's first administrator. From this moment the tenant is a durable, uniquely identified boundary: everything they subsequently create belongs to it, and no other tenant can observe or affect it.

**Why this priority**: Tenancy is the root of the entire data model and the security model. Every other requirement in this spec and every future slice depends on a tenant existing and being enforceable. Without it there is no product and no safe way to onboard a second customer.

**Independent Test**: Sign in as a new user, create a tenant, and confirm a unique tenant identifier is returned and the caller holds administrator rights within it. Then, signed in as a user belonging to a different tenant, confirm that tenant is entirely invisible — not listed, not readable by direct identifier, and not modifiable. This alone is a demonstrable, valuable slice: it proves safe multi-customer onboarding.

**Acceptance Scenarios**:

1. **Given** an authenticated user who belongs to no tenant, **When** they create a tenant with a valid display name, **Then** the tenant is persisted with a unique identifier, the creator is recorded as its administrator, and the tenant's details are returned to the caller.
2. **Given** an authenticated user who is an administrator of tenant A, **When** they request tenant B by its identifier, **Then** the request is refused and the response reveals nothing about whether tenant B exists.
3. **Given** an authenticated administrator of a tenant, **When** they update the tenant's display name to a valid value, **Then** the change is persisted and reflected in subsequent reads.
4. **Given** an unauthenticated caller, **When** they attempt any tenant operation, **Then** the request is rejected as unauthenticated and no tenant data is disclosed.
5. **Given** an authenticated user, **When** they list tenants, **Then** they see only tenants they are a member of.

---

### User Story 2 - Invite and manage tenant members (Priority: P2)

A tenant administrator invites colleagues by email address. An invited person accepts by signing in with their corporate identity, at which point they become a member of that tenant. The administrator can see the tenant's members and pending invitations, and can remove a member's access when they leave the organisation or change roles.

**Why this priority**: A single-user tenant has no collaborative value, and the platform's personas are inherently a group. This is required for a usable product but the tenant boundary from Story 1 must be correct first, because membership is what binds a user to that boundary.

**Independent Test**: As an administrator, invite an email address, confirm the invitation appears as pending, accept it as that person, and confirm they appear as an active member with the intended role and can read tenant data. Then remove them and confirm their access is gone.

**Acceptance Scenarios**:

1. **Given** an authenticated tenant administrator, **When** they invite an email address with a specified role, **Then** an invitation is recorded as pending against that tenant with that role and an expiry.
2. **Given** a pending invitation, **When** the invited person authenticates and accepts it, **Then** they become an active member of that tenant with the invited role, and the invitation is marked accepted and cannot be reused.
3. **Given** an expired or already-accepted invitation, **When** someone attempts to accept it, **Then** the attempt is refused and no membership is created.
4. **Given** an invitation issued to one email address, **When** a person authenticated as a different email address attempts to accept it, **Then** the attempt is refused.
5. **Given** an authenticated tenant administrator, **When** they remove an active member, **Then** that member immediately loses the ability to read or modify any of the tenant's data.
6. **Given** a tenant with exactly one administrator, **When** an attempt is made to remove or demote that administrator, **Then** the attempt is refused so the tenant cannot become unadministrable.

---

### User Story 3 - Enforce role-based permissions within a tenant (Priority: P2)

Not every member should be able to change tenant settings or manage membership. A member's role determines which operations they may perform. A reader can view tenant information; a member can act within the tenant; an administrator can additionally manage settings and membership.

**Why this priority**: Enterprise buyers will not adopt a platform where any member can remove other members or alter tenant configuration. It is equal in importance to Story 2 and is most cheaply built alongside it, since both concern membership.

**Independent Test**: For each role, attempt each tenant operation and confirm the outcome matches the intended permission matrix — permitted operations succeed, forbidden operations are refused as unauthorised rather than failing obscurely.

**Acceptance Scenarios**:

1. **Given** an authenticated member whose role is not administrator, **When** they attempt to invite or remove a member, **Then** the request is refused as unauthorised and membership is unchanged.
2. **Given** an authenticated member whose role is not administrator, **When** they read the tenant's details, **Then** the request succeeds.
3. **Given** an authenticated member whose role is reader, **When** they attempt to modify tenant settings, **Then** the request is refused as unauthorised.
4. **Given** an administrator, **When** they change another member's role to a valid role, **Then** that member's permissions change accordingly on their next request.

---

### Edge Cases

- **Duplicate tenant names**: two unrelated organisations may legitimately share a display name; identity is the tenant identifier, not the name. Names are not required to be globally unique.
- **User in multiple tenants**: a consultant may belong to several tenants. Every request must resolve to exactly one active tenant context, and data must never be blended across tenants in a single response.
- **Invitation to an address that is already a member**: refused as a conflict rather than creating a duplicate membership.
- **Invitation to an address with no corporate identity**: the invitation remains pending and expires; no membership is created.
- **Last administrator leaving**: prevented (Story 2, scenario 6) so a tenant cannot be orphaned.
- **Member removed mid-session**: a previously issued credential must not grant continued access beyond a bounded staleness window.
- **Tenant identifier that does not exist vs. exists but is inaccessible**: both must be indistinguishable to the caller, so tenant existence cannot be probed.
- **Concurrent conflicting membership edits**: two administrators editing the same member simultaneously must not produce a lost update or an inconsistent role.
- **Duplicate request delivery**: a tenant-creation or invitation request delivered twice must not produce two tenants or two invitations.
- **Database unavailable**: requests fail with a clear, non-leaking error, and the failure is logged with enough detail to diagnose. *(Dependency health reporting is S4.)*
- **Malformed or missing tenant context**: rejected rather than defaulting to any tenant.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication**

- **FR-001**: System MUST authenticate all callers against the organisation's corporate identity provider and MUST NOT store or manage user passwords itself.
- **FR-002**: System MUST reject every unauthenticated request to a non-public endpoint without disclosing any tenant or user data.
- **FR-003**: System MUST resolve each authenticated caller to a stable user identity that remains consistent across sessions.
- **FR-004**: System MUST reject credentials that are expired, malformed, or not issued for this platform.

**Tenancy**

- **FR-005**: System MUST allow an authenticated user to create a tenant, assigning it a unique identifier and recording the creator as its first administrator.
- **FR-006**: System MUST allow a tenant administrator to read and update their tenant's display name and settings.
- **FR-007**: System MUST resolve every request to exactly one active tenant context, and MUST reject any request whose tenant context is absent, malformed, or not one the caller belongs to.
- **FR-008**: System MUST prevent all cross-tenant data access, such that no response ever contains data belonging to a tenant the caller is not a member of.
- **FR-009**: System MUST make a tenant the caller cannot access indistinguishable from a tenant that does not exist.
- **FR-010**: System MUST support a single user holding membership in multiple tenants without blending their data.

**Membership & Invitations**

- **FR-011**: System MUST allow a tenant administrator to invite a person by email address with a specified role, recording the invitation as pending with an expiry.
- **FR-012**: System MUST allow an invited person, once authenticated as the invited email address, to accept a valid pending invitation and thereby become an active member with the invited role.
- **FR-013**: System MUST refuse acceptance of invitations that are expired, already accepted, revoked, or addressed to a different identity.
- **FR-014**: System MUST allow a tenant administrator to list members and pending invitations, revoke a pending invitation, remove an active member, and change a member's role.
- **FR-015**: System MUST guarantee every tenant retains at least one administrator, refusing any removal or demotion that would violate this.
- **FR-016**: System MUST revoke a removed member's effective access within a bounded, documented staleness window.

**Authorization**

- **FR-017**: System MUST assign each membership exactly one role from a defined set of at least Administrator, Member, and Reader.
- **FR-018**: System MUST evaluate every tenant-scoped operation against the caller's role in the active tenant and refuse unauthorised operations as forbidden, distinctly from unauthenticated.
- **FR-019**: System MUST restrict tenant settings changes and all membership management to administrators of that tenant.

**Reliability & Correctness**

- **FR-020**: System MUST treat tenant creation and invitation issuance idempotently, such that a duplicated request does not create duplicate records.
- **FR-021**: System MUST prevent lost updates when concurrent changes are made to the same tenant or membership.
- **FR-022**: System MUST return errors that identify the problem to the caller without disclosing internal detail or the existence of other tenants' data.

**Structure & Hygiene**

- **FR-023**: The tenancy capability MUST own its data exclusively; no other capability may read or write that data other than through its published interface.
- **FR-024**: The domain layer MUST NOT depend on infrastructure concerns. *(Automated enforcement of this boundary is S3; the code must satisfy it now regardless.)*
- **FR-025**: System MUST log every authentication outcome, tenant mutation, membership change, and authorisation refusal with enough structured detail to diagnose it, and MUST NOT log secrets or unnecessary personal data. *(Correlated tracing and the immutable audit store are S4.)*
- **FR-026**: No secret, credential, or connection string containing a secret may be committed to source control. Local development secrets MUST use a mechanism excluded from version control. *(Runtime retrieval via managed identity and Key Vault is S6.)*

### Key Entities

- **Tenant**: An isolated customer boundary. Has a unique identifier, a display name (not globally unique), status, settings, and creation metadata. Root of all tenant-scoped data.
- **User**: A person, identified by a stable identifier originating from the corporate identity provider, plus an email address and display name. Exists independently of any tenant and may belong to several.
- **Membership**: The relationship binding one User to one Tenant, carrying exactly one Role and a status. The unit that grants and revokes access.
- **Role**: A named permission set — at minimum Administrator, Member, Reader — determining which operations a Membership permits.
- **Invitation**: A pending offer of Membership to an email address for a Tenant, carrying an intended Role, an expiry, and a status of pending, accepted, revoked, or expired.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new administrator can go from first sign-in to a created tenant with one colleague invited in under 5 minutes without documentation or assistance.
- **SC-002**: An invited colleague can accept an invitation and reach tenant data in under 2 minutes from opening the invitation.
- **SC-003**: 95% of tenant read operations complete fast enough to feel immediate to the user (within 1 second) under a load of 50 concurrent users across 20 tenants.
- **SC-004**: 100% of attempted cross-tenant accesses are refused, verified by an automated isolation test suite covering every tenant-scoped operation, with zero exceptions permitted.
- **SC-005**: Two independent organisations can be onboarded and operated concurrently with no observable interference and no data visible across the boundary.
- **SC-006**: Automated tests cover every functional requirement above, and the full suite runs unattended in under 5 minutes.
- **SC-007**: Database migrations apply cleanly to an empty database and the application starts and serves requests with no manual setup step.
- **SC-008**: No secret appears anywhere in source control, verified by scanning the repository including its history.
- **SC-009**: The slice's architectural decisions are recorded as decision records, and any point where the blueprint in `idea.md` proved wrong is documented rather than silently worked around.

## Deferred Requirements

Removed from this slice during narrowing, retained here so the target slice's
specification can pick them up verbatim. Original FR/SC numbers are from the
pre-narrowing version of this document.

| Original | Requirement | Target slice |
|----------|-------------|--------------|
| FR-028 | Enforce architectural boundaries automatically, such that a violating change fails the build | **S3** |
| FR-023 | Emit logs, metrics, and distributed traces for every request, correlated by a single identifier spanning the entire request path | **S4** |
| FR-024 | Annotate telemetry with tenant and user identity without recording unnecessary personal data | **S4** |
| FR-025 | Expose health status covering the service and each critical dependency | **S4** |
| FR-026 | Record an immutable audit entry for every authentication outcome, tenant mutation, membership change, and authorisation refusal | **S4** |
| FR-029 | Be deployable as a container image through an automated pipeline gating on tests and vulnerability scanning, with production requiring human approval | **S5** (image) + **S7** (pipeline) |
| FR-030 | All infrastructure defined as code and reproducible into a clean environment | **S6** |
| FR-031 | Retrieve secrets at runtime from managed secret storage using workload identity rather than stored credentials | **S6** |
| SC-006 | An operator identifies the cause of a deliberately induced failure from telemetry alone in under 10 minutes | **S4** |
| SC-008 | A deliberate architectural boundary violation is rejected by the automated gate 100% of the time | **S3** |
| SC-007 | A commit reaches the development environment through the automated pipeline in under 20 minutes with no manual step | **S7** |
| SC-009 | The entire slice provisions into an empty Azure subscription from code alone and is verified healthy | **S6** |
| SC-011 | A security review of the deployed slice finds no secret in source control, container images, or logs | **S5**, **S7** |
| — | Audit Entry entity (actor, subject, action, time, source, outcome; immutable) | **S4** |

## Assumptions

1. **Identity provider**: Microsoft Entra ID is the corporate identity provider, consistent with `idea.md` §13 and §18. Users authenticate with existing organisational accounts; the platform manages no passwords. Self-service consumer sign-up is out of scope.
2. **Tenant model**: A shared-infrastructure, logically isolated model — isolation enforced in application and data access rather than by dedicated infrastructure per tenant. Physically isolated tenants are a later concern if a customer requires it.
3. **Persistence**: Azure SQL, run in a local container for this slice. The schema and access patterns must be the ones that will run in Azure, so that S6 is a deployment exercise rather than a rewrite.
4. **Deployment target**: The full architecture of `idea.md` §17 — AKS behind API Management, Terraform-provisioned, with managed identity, Key Vault, and private networking — remains the target and is delivered in S6. This slice must not make choices that obstruct it, but must not implement it either.
5. **Roles**: Three roles — Administrator, Member, Reader — are sufficient for this slice. Fine-grained or custom permissions are deferred until a concrete need appears.
6. **Invitation expiry**: Invitations expire after 7 days, an industry-standard default.
7. **Access-token staleness**: Credentials are short-lived enough that revoked access ends within one hour, satisfying FR-016 without per-request revocation checks.
8. **Invitation delivery**: Delivered by email. For this slice a development-time mechanism (logged or captured locally) is acceptable; the specification requires only that a pending invitation is recorded and acceptable.
9. **Scale**: The slice targets tens of tenants and hundreds of users — enough to prove the model, not to serve the eventual market.
10. **No AI**: Per `idea.md` §47, this slice contains no AI capability whatsoever. This is intentional and must not be relaxed.

## Dependencies

- A Microsoft Entra ID tenant with permission to register applications.
- A local container runtime for the database.
- An engineering constitution — **satisfied**, `.specify/memory/constitution.md` v1.0.0.
- A decision-record framework, so this slice's decisions can be recorded as it proceeds (roadmap S1). **Outstanding** — ADR-001, 002, 003 are prerequisites for planning this slice.

*No Azure subscription is required for this slice. That dependency begins at S6.*

## Non-Goals

**Deferred to a named slice** — tracked in [roadmap.md](../../roadmap.md), not dropped:

- Correlated tracing, metrics, health checks, immutable audit log → **S4**
- Automated architecture boundary enforcement → **S3**
- Container image → **S5**
- Terraform, Azure provisioning, managed identity, Key Vault → **S6**
- CI/CD pipeline and its gates → **S7**
- Asynchronous messaging and event publication → **S8**

**Excluded from the MVP entirely** (`idea.md` §46a):

Projects, programs, portfolios, teams, releases, milestones, risks, dependencies, or any other delivery-domain entity; any integration with Jira, Azure DevOps, GitHub, ServiceNow, PagerDuty, or observability platforms; any AI, agent, retrieval, or intelligence capability; any analytics, reporting, dashboard, or metric; billing, subscription, or plan management; tenant deletion or data export; custom or fine-grained permission models; user-facing interface beyond what is needed to demonstrate the acceptance scenarios.
