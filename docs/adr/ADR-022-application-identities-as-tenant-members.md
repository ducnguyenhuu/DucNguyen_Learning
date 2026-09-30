# ADR-022: A named application identity may be a tenant member, under an explicit token policy

**Status**: Accepted
**Date**: 2026-09-29
**Deciders**: Project owner (accepted 2026-09-29)
**Relates to**: Constitution → Principle I, IV, V · ADR-013 · ADR-017 · ADR-019 · `specs/006-ci-cd` research R7 · `specs/001-auth-tenant-management` SC-003 · roadmap S7

## Context

Roadmap S7 must verify spec 001 SC-003 — tenant reads under 1 s at 50 concurrent users across 20
tenants — against the deployed environment, from an unattended pipeline. Every tenant endpoint
requires an Entra ID bearer token, and today every caller is a human with a delegated token.

An unattended pipeline cannot obtain a delegated user token without storing a credential: the
resource owner password flow needs a stored password and fails under MFA; captured refresh tokens
are stored, long-lived, revocable credentials. Both violate Principle V.

Investigating this surfaced a latent gap. `Program.cs` wires `AddMicrosoftIdentityWebApi` and
enforces no scope or role. Microsoft.Identity.Web rejects tokens carrying neither `scp` nor
`roles`, so the API is safe today **only because its app registration defines no app roles**. The
first app role added to that registration for any purpose would silently admit every application
holding it as if it were a user.

## Decision

1. **The API authorizes by explicit policy.** A request is authorized only if its token carries the
   delegated scope `access_as_user`, **or** the app role `Tenancy.Automation.Member`. Every other
   token — including one with a different app role — is rejected with 403.
2. **One app role exists for automation**: `Tenancy.Automation.Member`, allowed member type
   *Application*, defined on the Tenancy API registration.
3. **It is assigned only to named, federated identities** — in Horizon 1, exactly one:
   `id-loadtest-client`, a user-assigned managed identity federated to this repository's `dev`
   environment. No secret exists for it.
4. **An application identity gets a member's powers and nothing more.** It is provisioned
   just-in-time from `tid` + `oid` exactly like a user, sees only tenants it is a member of, and
   becomes a member only by creating a tenant or being invited. No cross-tenant, platform-wide, or
   administrative capability is introduced.

## Consequences

### Positive

- The load test authenticates through the real path with no stored credential.
- The accepted-token set shrinks from "anything Entra issues with a scope or role" to a two-item
  allow-list — the latent gap is closed regardless of the load test.
- Tenant isolation needs no new mechanism; it applies to the application identity unchanged.

### Negative

- The API now has two caller kinds. Every future authorization rule must consider both.
- Audit and telemetry records will show a caller with a placeholder email
  (`{oid}@unresolved.invalid`) — correct, but less readable than a human's.

### Neutral / accepted trade-offs

- The load test runs 50 virtual users under one identity. Accepted because token validation is
  local and membership lookup is per `(tenant, oid)`; stated as a limitation in the load-test report.

## Alternatives Considered

### Resource owner password flow with dedicated test users

A stored password in the pipeline, broken by MFA. Rejected under Principle V.

### Refresh tokens captured interactively and stored as secrets

A stored, 90-day, revocable credential. Rejected under Principle V.

### A test-only authentication scheme in the deployed dev build

A backdoor in a deployed artifact, one configuration flag from reaching production. Rejected.

### Load from inside the cluster, bypassing Front Door and APIM

Does not measure the path SC-003 is about, and still needs an identity. Rejected.

## Revisit When

- A second automation caller is proposed — each must be named here, not granted the role ad hoc.
- A production environment is created — the role assignment must not follow the dev identity there
  without a separate decision.
- Customer-directory sign-in (deferred by ADR-019) arrives — the `tid` of an application identity
  must still resolve to this platform's own directory.

## Compliance

- Unit tests: each token shape — delegated with scope, application with the role, application with
  another role, neither — is accepted or rejected as stated in Decision 1.
- Integration tests: the application identity is refused on a tenant it is not a member of, with
  the same response as a non-member user (Principle IV: indistinguishable from non-existent).
- The role assignment exists only in `infrastructure/terraform/persistent/` and only for
  `id-loadtest-client`.
