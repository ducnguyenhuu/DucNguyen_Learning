---
name: security
description: Use when touching authentication, authorization, membership, credentials, or any code path that accepts untrusted input.
---

# Security

Governed by [Constitution Principle V](../../../.specify/memory/constitution.md) and
[ADR-025](../../../docs/adr/ADR-025-single-organization.md). One deployment serves one
organization: there are no tenants, and Principle IV is retired.

## Authorization comes from the database, never from the token

The token says **who** the caller is. Only the caller's active `Membership` row says
**what** they may do.

### The three mechanisms, in order of reliance

1. **Membership resolved once per request**, in **one** seam: `MembershipResolutionFilter`,
   opted into per route group with `RequireMembership()`. It looks the caller up by the
   token's `(tid, oid)` pair and loads their active membership. No membership means
   **403**. Never resolve membership per endpoint.
2. **Role checks read `ICallerContext.Role`**, the resolved membership's role, through
   `RequireAdministrator()`. A role, scope or group claim on the token is the caller's own
   assertion and is never an authorization input. The automation app role (ADR-022) admits
   a caller; it grants no role.
3. **Automated authorization tests** for every member-only and administrator-only route.
   A route without one is not done.

### The routes that run without membership

Exactly three, because their caller may not be a member yet: `GET /me`,
`POST /members/bootstrap` and `POST /invitations/{token}/accept`. A fourth needs ADR-025
amended. Bootstrap also refuses any token without the delegated scope: an application
identity must never become the first administrator.

## Authentication

- Microsoft Entra ID. **The platform never stores or manages passwords** (FR-001).
- Validate token expiry, signature, issuer, and audience. A token not issued for this
  platform is rejected (FR-004).
- Resolve to a stable user identity that survives across sessions (FR-003). The key is
  `(EntraTenantId, EntraObjectId)` — "tenant" there is Entra's directory, not ours
  (ADR-019).
- Revoked access ends within one hour — short-lived tokens rather than per-request
  revocation checks (FR-016, Assumption 7). **This is a known trade-off:** a removed
  member retains access for up to an hour.

## Authorization

Three roles: `Administrator`, `Member`, `Reader`.

- Administrators only: all membership and invitation management (FR-019)
- `401` unauthenticated and `403` unauthorized are **distinct** to the caller (FR-018)
- Invariant: the organization always retains at least one administrator (FR-015),
  enforced under an application lock so concurrent removals cannot both pass

## Secrets

- **Nothing secret in source control, ever.** Not in `appsettings.json`, not in
  Terraform variables, not in test fixtures, not in a comment. A secret committed once
  is compromised forever, even after removal — the fix is rotation, not deletion.
- Local: .NET User Secrets. Azure: Key Vault via managed identity.
- **No connection strings containing credentials.** Managed identity to SQL and Key Vault
  (Principle V).
- Never log a secret, a token, or a full authorization header.
- Credentials for external systems (slice 9) are stored as **Key Vault references** —
  never as values in our database.

## Untrusted input

- Validate at the boundary; reject rather than coerce.
- Parameterized queries only. String-concatenated SQL is prohibited.
- Errors identify the problem without disclosing internals (FR-022).
- Email addresses in invitations are untrusted until the invited identity authenticates
  as that address (FR-013).

## Rationalizations that mean you're about to open a hole

| Thought | Reality |
|---------|---------|
| "The token already has an Admin role claim, I'll just check that" | The claim is the caller's assertion. Roles come from the membership row, or a removed administrator keeps their powers until the token expires — and any app role holder becomes one. |
| "This endpoint is read-only, it doesn't need membership" | Reading the organization's data is access. Only the three routes above run without membership. |
| "It's an internal admin tool, no external user hits it" | Internal-only today is exposed tomorrow. Authorization rules have no "internal" exemption. |
| "I'll add the authorization test after this ships" | A member-only route without a test proving a non-member is refused is not done. |
| "This log line has the user ID but not the secret, so it's fine" | Check what's actually in the object being logged — a full auth header or token often rides along with debug context. |

## Red flags — stop and re-check

- A role or permission read from a token claim instead of `ICallerContext`
- A member-only endpoint resolving the caller itself instead of using `RequireMembership()`
- `RequireAdministrator()` chained before `RequireMembership()` — it would read an unresolved caller
- A new route that runs without membership, beyond the three listed above
- A new member-only or administrator-only route with no authorization test in the same PR
- A secret, token, or connection string anywhere in a config file, fixture, or log statement

## Before you commit

- [ ] Does every new route either use `RequireMembership()` or appear in the list of three?
- [ ] Does every new administrator-only route use `RequireAdministrator()` after it?
- [ ] Does every new route have a test proving the wrong caller is refused?
- [ ] Any secret, token, or PII in a log line or a telemetry attribute?
- [ ] Any new raw SQL? If so, is it parameterized and on the `RawSqlGates` allow-list?

## The research-first bar

`idea.md` §59.2: **authorization is not proven until an automated test has actually caught
a non-member and a non-administrator being refused.** Write the failing test first, watch
it fail, then make it pass. A passing test that never could have failed proves nothing.
