# ADR-019: One Entra tenant in Horizon 1; multi-directory sign-in deferred

**Status**: Accepted
**Date**: 2026-08-10
**Deciders**: Project owner
**Relates to**: Constitution → Principle IV, Principle X · ADR-013 · ADR-017 · `specs/001-auth-tenant-management` FR-001, FR-003, SC-005, Assumption 1 · roadmap S2

## Context

Spec 001 Assumption 1 says users *"authenticate with existing organisational accounts"*, and
SC-005 requires *"two independent organisations onboarded and operated concurrently"*. Read
together, those imply customer users signing in from **their own** Entra directories.

The implementation does not do that. `infrastructure/scripts/create-entra-app-registrations.sh`
registers the API with `--sign-in-audience AzureADMyOrg` — **one Entra tenant only**. A user
homed in a second organisation's Entra directory cannot obtain a token at all, so SC-005 as
written is unsatisfiable in S2.

This was found by the security requirements-quality checklist
([checklists/security.md](../../specs/001-auth-tenant-management/checklists/security.md) K1),
not by the three earlier review passes — because it is a conflict between a requirement and a
shell script, and the earlier passes compared artifacts against each other.

**The data model already anticipated the multi-directory case.** `User` is keyed on the composite
`(EntraTenantId, EntraObjectId)` precisely because `oid` is unique only *within* an Entra tenant
(research.md R2). So the seam exists; only the configuration forbids using it.

## Decision

**Horizon 1 uses one Entra tenant.** Multi-directory sign-in — customer users authenticating from
their own Entra directories — is **deferred**, not designed out.

Three consequences of that, stated so they cannot drift:

1. **The app registration stays `AzureADMyOrg`** (single tenant). Issuer validation therefore has
   exactly one valid issuer, which is the simplest correct configuration.
2. **`User` keeps its composite `(EntraTenantId, EntraObjectId)` key**, even though `EntraTenantId`
   is constant in Horizon 1. Collapsing it to `oid` alone would look like a simplification and
   would be a latent defect — it is precisely the assumption that breaks the moment a second
   directory or a B2B guest appears.
3. **SC-005 is split.** Its isolation half stays in S2 and must be proven; its multi-directory
   sign-in half moves to a later slice. See Compliance.

**This is a research-project scope decision, not a product position.** Commercial multi-tenancy
will need one of the alternatives below, and the expected answer is Entra B2B.

## Consequences

### Positive

- **S2 stays verifiable on a development machine**, which is the whole premise of the slice. Both
  alternatives break that: multi-tenant registration needs a second Entra directory to test
  against, which S2's Dependencies explicitly exclude.
- No admin-consent dependency. Multi-tenant registration requires each customer's Entra
  administrator to consent, which is a procurement conversation rather than an engineering task —
  a poor thing to put on the critical path of the first code slice.
- Nothing is built for an anticipated need (Principle X). The seam is created; the implementation
  is deferred, which is what that principle actually prescribes.
- Isolation — the property that matters and the one Principle IV calls existential — is fully
  provable in S2 with two platform tenants and test users from one directory.

### Negative

- **SC-005 cannot be satisfied as originally written.** This is the real cost, and it is why the
  criterion is being split rather than quietly marked green.
- The limitation is invisible from the code: nothing in the codebase fails or warns when only one
  Entra tenant is usable. It lives in configuration and in this ADR.
- **Deferred work has a habit of not being scheduled.** Gate 1 does not check multi-directory
  sign-in, so nothing forces the issue. Mitigated only by the Compliance entry below.
- A demo to a real prospective customer would need their users invited as guests first, which is
  an onboarding step the product does not model.

### Neutral / accepted trade-offs

- Every user in Horizon 1 shares one `tid`. Code must still read it and must not assume it is
  constant — see Compliance.
- Platform tenants and Entra tenants remain independent concepts (`docs/architecture/domain-model.md`).
  This ADR does not couple them; it only limits how many of the latter exist.

## Alternatives Considered

### Entra B2B — invite customer users as guests into the platform's own directory

The likely eventual answer, and the strongest alternative. Guests sign in with their own corporate
credentials via home-realm discovery, while their identity object lives in our directory.
Requires **no admin consent from customer IT**, which is its decisive practical advantage, and
revoking a guest cuts access at the identity layer — which would strengthen FR-016.

Rejected for S2 because it introduces a **second invitation system** (Entra B2B invitations
alongside spec 001's own `Invitation` aggregate) before the first has been built or proven. Two
overlapping invitation flows in the slice that introduces invitations is a poor trade. It also
makes us the operator of a directory containing customer identities, which is a real
responsibility to take on before there is a customer.

### Multi-tenant app registration (`AzureADMultipleOrgs`) with a `tid` allow-list

The "real" SaaS shape, and the one the data model was designed for. Customer users stay in their
own directories; we store no identity objects.

Rejected for S2 on two grounds. It **cannot be tested without a second Entra directory**, which
S2's Dependencies exclude and which would undermine the slice's local-verifiability premise. And
it requires per-customer admin consent, putting an external, non-engineering dependency on the
first code slice.

**Recorded as a hazard for whenever this is revisited:** a multi-tenant registration without an
explicit allow-list of accepted `tid` values lets **any Entra tenant in the world** authenticate.
The default issuer validation accepts any issuer matching the multi-tenant pattern, so it must be
augmented with a check against directories that have actually been onboarded. This is a security
defect, not a configuration preference, and it is the single thing most likely to be got wrong by
someone implementing this option quickly.

## Revisit When

- **A real prospective customer needs their own users to sign in.** The most likely trigger, and
  the expected answer is Entra B2B rather than a multi-tenant registration.
- A second Entra directory becomes available for testing, which removes the main practical
  objection to the multi-tenant option.
- Guest-account management becomes burdensome enough to make multi-tenant registration worth its
  consent cost.

## Compliance

- **The app registration remains single-tenant** until this ADR is superseded. The bootstrap
  script's `--sign-in-audience AzureADMyOrg` is the enforcement point, and it is committed.
- **`User` MUST keep the composite `(EntraTenantId, EntraObjectId)` key.** Reducing it to `oid`
  alone is prohibited — it is the change that would turn this deferral into a migration.
- **Code MUST NOT assume `tid` is constant.** Read it from the token and store it; do not hardcode
  it or omit it from the identity lookup.
- **SC-005 is split** in spec 001: the isolation half (two platform tenants, no cross-visibility)
  is proven in S2 by the isolation suite; the multi-directory sign-in half is recorded in Deferred
  Requirements against a later slice.
- **Not silently forgotten**: recorded in spec 001's Deferred Requirements, in
  `checklists/security.md` K1, and here. If none of those is read before Horizon 2, that is the
  failure mode this ADR could not prevent.
