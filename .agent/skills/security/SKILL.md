---
name: security
description: Use when touching authentication, authorization, tenancy, credentials, or any code path that accepts untrusted input.
---

# Security

Governed by [Constitution Principles IV and V](../../../.specify/memory/constitution.md)
and [ADR-013](../../../docs/adr/ADR-013-multi-tenancy-model.md).

## Tenant isolation is the one that ends the company

This platform holds customers' delivery and engineering data. **A single cross-tenant
leak is existential, not a bug to fix next sprint.** Treat every rule below as
load-bearing.

### The four mechanisms, in order of reliance

1. **Global query filter** at the data-access layer. Tenant filtering is applied by
   default, never written per query — a developer must not be able to omit it by
   forgetting.
2. **Tenant context resolved once per request** from the authenticated principal's
   membership — in **one** seam, never per endpoint.

   A caller in several tenants must be able to say which one they mean (FR-010), so a
   client-supplied value is unavoidable. The distinction that matters
   ([ADR-017](../../../docs/adr/ADR-017-tenant-context-resolution.md)):

   > The client may **name** a candidate tenant. It may never **grant** itself access to one.

   The route value is an *input* to a server-side membership lookup keyed on the
   authenticated principal — never a substitute for it. Fail **closed**: no active
   membership means 404, identical to a tenant that does not exist. Using a route, query,
   header, or body value **as the authorization decision itself** is the IDOR
   vulnerability this rule exists to prevent.
3. **Authorization evaluated against membership** in the resolved tenant, on every
   tenant-scoped operation.
4. **Automated isolation tests** for every tenant-scoped operation. This is a release
   gate, not ordinary test coverage (spec 001 SC-004 permits zero exceptions).

### The rule people forget

**Non-existence and inaccessibility must be indistinguishable.** A tenant you cannot
access returns exactly what a tenant that does not exist returns. Otherwise tenant
existence is probeable.

```csharp
// WRONG — leaks existence
var tenant = await db.Tenants.FindAsync(id);          // bypasses the filter
if (tenant is null) return NotFound();
if (!await IsMember(user, id)) return Forbid();        // now they know it exists

// RIGHT — the filter makes it invisible; one response for both cases
var tenant = await db.Tenants.SingleOrDefaultAsync(t => t.Id == id, ct);
if (tenant is null) return NotFound();
```

### Where isolation actually breaks

Not in the obvious query. In these:

- **Background jobs** running with no request context, so no tenant context — the single
  most likely route to a leak under ADR-013's model, and **currently unguarded**
  (traceability U12, assigned to slice 3)
- **Raw SQL** and stored procedures, which bypass the global filter entirely
- **Bulk exports and reports**, which are often written as raw SQL for performance
- **Vector indexes, embeddings, and AI context** (slice 13+) — an index shared across
  tenants leaks exactly as effectively as a missing predicate and far less visibly
- **Cache keys** missing the tenant identifier
- **Event handlers** consuming a message without re-establishing tenant context

Every one of these needs tenant scoping designed in, not added.

## Authentication

- Microsoft Entra ID. **The platform never stores or manages passwords** (FR-001).
- Validate token expiry, signature, issuer, and audience. A token not issued for this
  platform is rejected (FR-004).
- Resolve to a stable user identity that survives across sessions (FR-003).
- Revoked access ends within one hour — short-lived tokens rather than per-request
  revocation checks (FR-016, Assumption 7). **This is a known trade-off:** a removed
  member retains access for up to an hour.

## Authorization

Three roles: `Administrator`, `Member`, `Reader`.

- Administrators only: tenant settings, all membership management (FR-019)
- `401` unauthenticated and `403` unauthorized are **distinct** to the caller (FR-018)
- Invariant: a tenant always retains at least one administrator (FR-015)

## Secrets

- **Nothing secret in source control, ever.** Not in `appsettings.json`, not in
  Terraform variables, not in test fixtures, not in a comment. A secret committed once
  is compromised forever, even after removal — the fix is rotation, not deletion.
- Local: .NET User Secrets. Azure: Key Vault via managed identity.
- **No connection strings containing credentials.** Managed identity to SQL and Key Vault
  (Principle V).
- Never log a secret, a token, or a full authorization header.
- Credentials for external systems (slice 9) are stored as **Key Vault references**, per
  tenant — never as values in our database.

## Untrusted input

- Validate at the boundary; reject rather than coerce.
- Parameterized queries only. String-concatenated SQL is prohibited.
- Errors identify the problem without disclosing internals or other tenants' existence
  (FR-022).
- Email addresses in invitations are untrusted until the invited identity authenticates
  as that address (FR-013).

## Rationalizations that mean you're about to cause a leak

| Thought | Reality |
|---------|---------|
| "It's an internal admin tool, no external user hits it" | Internal tools still run against real tenant data, and internal-only today is exposed tomorrow. Isolation rules don't have an "internal" exemption. |
| "This background job only ever runs for one tenant anyway" | It has no request, so it has no tenant context by default. "Only ever" is an assumption about today's callers, not a guarantee the code enforces. |
| "Raw SQL is faster for this report / bulk export" | Raw SQL bypasses the one mechanism that makes leaks structurally hard. Faster and unscoped is not a trade worth making with customer data. |
| "I'll add the isolation test after this ships" | Spec 001 SC-004 permits zero exceptions. A tenant-scoped operation without a test is not "done, tested later" — it's not done. |
| "Returning 403 here is more honest than a generic 404" | More honest to the attacker is exactly the problem — it confirms the tenant exists. Non-existence and inaccessibility must be indistinguishable. |
| "This log line has the tenant ID but not the secret, so it's fine" | The rule is about secrets and PII, but check what's actually in the object being logged — a full auth header or token often rides along with debug context. |

## Red flags — stop and re-check

- A tenant taken from a route, header, or body value **without** a membership lookup against the authenticated principal
- A tenant-scoped endpoint resolving its own context instead of going through the single resolution seam
- A non-member receiving 403 instead of 404 — that response confirms the tenant exists
- Raw SQL or a stored procedure touching tenant-scoped data
- A background job or event handler with no explicit tenant context
- A new tenant-scoped endpoint with no isolation test in the same PR
- Any response that reveals whether a resource *exists* before confirming the caller can *access* it
- A secret, token, or connection string anywhere in a config file, fixture, or log statement

**All of these mean: stop, re-check against the four mechanisms above, and do not ship until resolved — this is the one category of bug this platform cannot absorb.**

## Before you commit

- [ ] Does every new query rely on the global tenant filter?
- [ ] Does every new tenant-scoped operation have an isolation test?
- [ ] Does any new background job or event handler establish tenant context explicitly?
- [ ] Any secret, token, or PII in a log line or a telemetry attribute?
- [ ] Any new raw SQL? If so, how is tenant scoping guaranteed?

## The research-first bar

`idea.md` §59.2: **multi-tenancy is not proven until an automated test has actually
caught an attempted cross-tenant read.** Write the failing test first, watch it fail,
then make it pass. A passing test that never could have failed proves nothing.
