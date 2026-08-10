# Feature Specification: Authentication & Tenant Management

**Feature Branch**: `001-auth-tenant-management`
**Created**: 2026-08-08
**Narrowed**: 2026-08-08 — scope reduced to slice S2 (see Revision Note)
**Reviewed**: 2026-08-09 — consistency check after planning; see [Post-Planning Review](#post-planning-review)
**Status**: **Planned** — `/speckit.plan` complete ([plan.md](plan.md)). Awaiting `/speckit.tasks`.
**Roadmap slice**: **S2** — Auth + Tenant + Persistence (local). See [roadmap.md](../../roadmap.md).
**Governing decisions**: [ADR-013](../../docs/adr/ADR-013-multi-tenancy-model.md) (tenancy model) · [ADR-017](../../docs/adr/ADR-017-tenant-context-resolution.md) (how FR-007's tenant context is resolved)
**Input**: First code slice of the AI Engineering & Delivery Intelligence Platform, per `idea.md` §47. Deliberately contains no AI capability.

## Revision Note

This specification originally also covered observability, containerization,
Terraform/Azure provisioning, and CI/CD as a fourth user story. That made it span
roadmap slices S2 through S7 — roughly six slices of work behind one heading, which
is the "large incomplete technical layer" `idea.md` §29 prohibits.

It has been narrowed to **S2 only**. Everything removed is recorded in
[Deferred Requirements](#deferred-requirements) with its target slice, so nothing is
lost. Gate 1 in roadmap.md still requires all of S2–S8 before Horizon 2 begins.

## Post-Planning Review

**2026-08-09.** Re-read against everything decided after this specification was written:
ADR-017, ADR-018, the SC-003 deferral, and the S2 plan. Six inconsistencies found and fixed;
**no functional requirement changed**, and none was added or removed.

| # | Drift | Fix |
|---|---|---|
| 1 | **Numbering collision** — the Deferred Requirements table reused FR-023..FR-026 and SC-006..SC-009 for *different* requirements than the live ones above. Genuinely misleading to anyone adopting them in S3–S7. | Prefixed `old-`, split into two tables, with an instruction to renumber on adoption |
| 2 | **Dependencies claimed the ADR framework was outstanding** — "ADR-001, 002, 003 are prerequisites", status *Outstanding*. S1 completed them on 2026-08-08. | Marked satisfied; twelve ADRs now exist |
| 3 | **Status still `Draft`** after planning completed | → `Planned` |
| 4 | **Non-Goals excluded "observability platforms"** — ambiguous once ADR-018 made New Relic *our* telemetry backend | Clarified: the exclusion is about ingesting delivery data *from* them, not our own telemetry |
| 5 | **Assumption 3 said "Azure SQL, run in a local container"** — Azure SQL is a managed service with no container form | Restated as SQL Server standing in for Azure SQL, and named the erosion risk |
| 6 | **SC-003 had no verification scheduled anywhere** | Deferred to S7, recorded in the spec, U6, and S7's *Done when* |

**What did *not* need changing, and why that matters more than the fixes:**

- **ADR-018 changed the telemetry backend from Application Insights to New Relic, and this
  specification needed no edit** beyond the wording clarification in #4. The deferred telemetry
  requirements describe *correlated traces, metrics, logs, health, and audit* without naming a
  product. That is the requirement written at the right altitude.
- **ADR-017 settled how FR-007's tenant context is resolved** — a route selector validated
  against membership — and FR-007 needed no change either. It states the *what* ("resolve to
  exactly one tenant context; reject if absent, malformed, or not one the caller belongs to");
  the ADR supplies the *how*. A pointer was added to the header rather than a mechanism to the
  requirement.

Both are evidence the narrowing put things at the right layer. Had an implementation decision
forced a requirement to change, that would have been the signal this specification was
over-specified.

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
- **SC-003**: 95% of tenant read operations complete fast enough to feel immediate to the user (within 1 second) under a load of 50 concurrent users across 20 tenants. *(Requirement stands; **verification deferred to S7** — see [Deferred Requirements](#deferred-requirements). Measuring on S2's locally emulated database would produce a meaningless number.)*
- **SC-004**: 100% of attempted cross-tenant accesses are refused, verified by an automated isolation test suite covering every tenant-scoped operation, with zero exceptions permitted.
- **SC-005**: Two independent organisations can be onboarded and operated concurrently with no observable interference and no data visible across the boundary.
- **SC-006**: Automated tests cover every functional requirement above, and the full suite runs unattended in under 5 minutes.
- **SC-007**: Database migrations apply cleanly to an empty database and the application starts and serves requests with no manual setup step.
- **SC-008**: No secret appears anywhere in source control, verified by scanning the repository including its history.
- **SC-009**: The slice's architectural decisions are recorded as decision records, and any point where the blueprint in `idea.md` proved wrong is documented rather than silently worked around.

## Deferred Requirements

Nothing here is dropped — each item names the slice that picks it up.

> ⚠️ **Read the identifiers carefully.** The table below uses **pre-narrowing** numbering,
> which *collides* with the live numbering in this document: old FR-023..FR-026 and old
> SC-006..SC-009 are **different requirements** from the current FR-023..FR-026 and
> SC-006..SC-009 above. They are prefixed `old-` here to make that unambiguous. When a target
> slice adopts one, it should **renumber it into its own sequence** rather than carrying the
> old identifier forward. *(Collision noticed during the 2026-08-09 consistency review.)*

### A. Removed during narrowing — pre-narrowing numbering

| Old ref | Requirement | Target slice |
|----------|-------------|--------------|
| `old-FR-028` | Enforce architectural boundaries automatically, such that a violating change fails the build | **S3** |
| `old-FR-023` | Emit logs, metrics, and distributed traces for every request, correlated by a single identifier spanning the entire request path | **S4** |
| `old-FR-024` | Annotate telemetry with tenant and user identity without recording unnecessary personal data | **S4** |
| `old-FR-025` | Expose health status covering the service and each critical dependency | **S4** |
| `old-FR-026` | Record an immutable audit entry for every authentication outcome, tenant mutation, membership change, and authorisation refusal | **S4** |
| `old-FR-029` | Be deployable as a container image through an automated pipeline gating on tests and vulnerability scanning, with production requiring human approval | **S5** (image) + **S7** (pipeline) |
| `old-FR-030` | All infrastructure defined as code and reproducible into a clean environment | **S6** |
| `old-FR-031` | Retrieve secrets at runtime from managed secret storage using workload identity rather than stored credentials | **S6** |
| `old-SC-006` | An operator identifies the cause of a deliberately induced failure from telemetry alone in under 10 minutes | **S4** |
| `old-SC-008` | A deliberate architectural boundary violation is rejected by the automated gate 100% of the time | **S3** |
| `old-SC-007` | A commit reaches the development environment through the automated pipeline in under 20 minutes with no manual step | **S7** |
| `old-SC-009` | The entire slice provisions into an empty Azure subscription from code alone and is verified healthy | **S6** |
| `old-SC-011` | A security review of the deployed slice finds no secret in source control, container images, or logs | **S5**, **S7** |
| — | Audit Entry entity (actor, subject, action, time, source, outcome; immutable) | **S4** |

None of the telemetry items above names a backend, which is why
[ADR-018](../../docs/adr/ADR-018-new-relic-telemetry-backend.md)'s change of telemetry backend
from Application Insights to New Relic required **no change to this specification**. That is
the requirement being written at the right level of abstraction, and it is worth noticing.

### B. Deferred after planning — current numbering

| Ref | What moves | Target slice |
|---|---|---|
| **SC-003** | **Verification only.** The requirement itself stays in force for this slice's design — indexing and query shape are constrained by it. Only the load test that proves it moves. | **S7** |

**Why SC-003 moved** (decided 2026-08-09, [traceability U6](../../docs/traceability.md#u6--22-lists-eight-test-types-only-four-are-scheduled)):
raised during S2 planning because SC-003 had no verification scheduled anywhere and roadmap S2's
*Done when* omitted it — so it was on course to pass unverified and unmarked. S7 is the earliest
slice with both a pipeline to run a load test **and** a deployed environment to run it against,
and is still before Gate 1, so this specification remains fully verified before Horizon 2.
Measuring in S2 was rejected because S2's database is SQL Server under x86 emulation on an ARM
development machine — the number would say nothing about Azure SQL.

## Assumptions

1. **Identity provider**: Microsoft Entra ID is the corporate identity provider, consistent with `idea.md` §13 and §18. Users authenticate with existing organisational accounts; the platform manages no passwords. Self-service consumer sign-up is out of scope.
2. **Tenant model**: A shared-infrastructure, logically isolated model — isolation enforced in application and data access rather than by dedicated infrastructure per tenant. Physically isolated tenants are a later concern if a customer requires it.
3. **Persistence**: Azure SQL is the target. For this slice it is stood in for by **SQL Server in a local container** — Azure SQL itself is a managed service with no container form, so the local database is a compatible substitute, not the same product. The schema and access patterns must be the ones that will run on Azure SQL, so that S6 is a deployment exercise rather than a rewrite. *(This assumption is the one most likely to erode silently; the planning checklist flags it as needing an explicit check.)*
4. **Deployment target**: The full architecture of `idea.md` §17 — AKS behind API Management, Terraform-provisioned, with managed identity, Key Vault, and private networking — remains the target and is delivered in S6. This slice must not make choices that obstruct it, but must not implement it either.
5. **Roles**: Three roles — Administrator, Member, Reader — are sufficient for this slice. Fine-grained or custom permissions are deferred until a concrete need appears.
6. **Invitation expiry**: Invitations expire after 7 days, an industry-standard default.
7. **Access-token staleness**: Credentials are short-lived enough that revoked access ends within one hour, satisfying FR-016 without per-request revocation checks.
8. **Invitation delivery**: Delivered by email. For this slice a development-time mechanism (logged or captured locally) is acceptable; the specification requires only that a pending invitation is recorded and acceptable.
9. **Scale**: The slice targets tens of tenants and hundreds of users — enough to prove the model, not to serve the eventual market.
10. **No AI**: Per `idea.md` §47, this slice contains no AI capability whatsoever. This is intentional and must not be relaxed.

## Dependencies

- A Microsoft Entra ID tenant with permission to register applications. **Outstanding — the only remaining blocker.** Needs a human; see [quickstart.md](quickstart.md) §1. No Azure subscription required.
- A local container runtime for the database. *(Note for Apple Silicon: SQL Server has no native ARM64 build and runs emulated — see [research.md](research.md) R5 for the image to pin and the one to avoid.)*
- An engineering constitution — **satisfied**, `.specify/memory/constitution.md` v1.0.0.
- A decision-record framework, so this slice's decisions can be recorded as it proceeds (roadmap S1). **Satisfied** — S1 is complete: [docs/adr/](../../docs/adr/) holds the framework, template, and twelve ADRs. ADR-001, 002, and 003 all exist and were cited during planning; ADR-017 was raised *by* this slice's planning and accepted.

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

Projects, programs, portfolios, teams, releases, milestones, risks, dependencies, or any other delivery-domain entity; any integration with Jira, Azure DevOps, GitHub, ServiceNow, PagerDuty, or observability platforms **as data sources**; any AI, agent, retrieval, or intelligence capability; any analytics, reporting, dashboard, or metric; billing, subscription, or plan management; tenant deletion or data export; custom or fine-grained permission models; user-facing interface beyond what is needed to demonstrate the acceptance scenarios.

*Clarification (2026-08-09):* "observability platforms" above means **ingesting delivery data
from** them as a source for the product's intelligence. It does not refer to the platform's own
telemetry backend, which is New Relic per
[ADR-018](../../docs/adr/ADR-018-new-relic-telemetry-backend.md) and arrives in S4. The two are
unrelated concerns that happen to share a vocabulary.
