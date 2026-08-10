# ADR-017: Tenant context is resolved from a validated route selector

**Status**: **Accepted**
**Date**: 2026-08-09
**Deciders**: Project owner
**Relates to**: Constitution → Principle IV · ADR-013 · `specs/001-auth-tenant-management` FR-007, FR-009, FR-010 · roadmap S2

## Context

ADR-013 chose shared infrastructure with logical isolation, and required tenant context to
be "resolved once per request from the authenticated principal's membership, never from a
client-supplied parameter that is **trusted**".

It did not specify *how* a caller indicates which tenant they mean. That gap is now forced,
because spec 001 requires both of the following at once:

- **FR-010**: a single user may hold membership in multiple tenants (a consultant is the
  motivating case, per `idea.md` §19).
- **FR-007**: every request MUST resolve to exactly **one** active tenant context, and MUST
  be rejected if that context is absent, malformed, or not one the caller belongs to.

A caller in three tenants must therefore be able to name one. Something client-supplied is
unavoidable — the question is what that something is permitted to *do*.

The `security` agent skill states the rule more absolutely than ADR-013 does: "Never from a
route parameter, query string, header, or body the caller controls." Read literally, that
forbids the only mechanism satisfying FR-010. Principle II requires this be raised rather
than worked around, which is why this ADR exists instead of a quiet implementation choice.

## Decision

Tenant context is resolved from a **route selector that is validated, never trusted**:

```
/tenants/{tenantId}/...
```

The governing distinction:

> The client may **name** a candidate tenant. It may never **grant** itself access to one.

Concretely, on every tenant-scoped request:

1. `{tenantId}` is parsed as a **candidate**. It confers nothing.
2. An **active membership** is looked up for `(authenticated principal, candidate tenant)`.
   The principal comes from the validated token's `(tid, oid)` claims, never from the
   request body or headers.
3. If no active membership exists, the request fails **closed** with `404`, identical to the
   response for a tenant that does not exist (FR-009). No `403`, because `403` would confirm
   the tenant exists.
4. Only if a membership is found is a tenant context established, and it is then **fixed for
   the lifetime of the request scope** — including the `DbContext`, so one scope never sees
   two tenants.
5. Role authorization is evaluated against **that membership**, not against the token.

`403` is reserved for a caller who **is** an active member but whose role does not permit the
operation (FR-018). The distinction is deliberate: `404` hides existence from non-members,
`403` reports insufficient privilege to members.

### The enumerated exceptions

Exactly three operations run without a resolved tenant context. The list is closed; adding a
fourth requires amending this ADR.

| Operation | Why | Compensating control |
|---|---|---|
| `POST /tenants` | No tenant exists yet. | No tenant-scoped read occurs. Creator becomes first Administrator in the same transaction. |
| `GET /tenants` | Lists the caller's memberships, which span tenants by definition. | Single audited helper. Queries `Membership` by `UserId`. Bypasses **only** the named tenant filter, never all filters. `UserId == caller` is not optional. |
| `POST /invitations/{token}/accept` | The caller has no membership — creating one is the point. | Authorized by invitation token plus identity match (FR-013), not by membership. |

Enumerating them is the control. An unlisted exception is how a filter gets bypassed a
fourth time without anyone noticing.

## Consequences

### Positive

- The tenant a request touches is **visible in the URL**, so it appears in logs, traces,
  metrics, and cache keys without extra work — directly serving Principle VI when S4 adds
  telemetry.
- "One tenant per request" becomes structural rather than conventional: there is nowhere in
  the route for a second tenant to appear.
- Idiomatic REST sub-resource modelling, so the API shape needs no explanation.
- Failing closed with `404` satisfies FR-009 by construction rather than by remembering to
  special-case it per endpoint.

### Negative

- **The membership lookup is on the hot path of every tenant-scoped request.** It must be
  cheap; a covering index on `(TenantId, UserId)` filtered to active memberships is not
  optional. Caching it would introduce a staleness window on *authorization*, which is a
  different and worse risk than FR-016's token staleness — so it is not cached in this slice.
- A tenant identifier in the URL is **not** a secret but is a visible identifier, so it will
  appear in browser history, proxy logs, and referrer headers. Acceptable: knowing an opaque
  identifier grants nothing.
- Callers must carry the tenant id, which makes client code marginally more verbose than an
  implicit session-held tenant.

### Neutral / accepted trade-offs

- `GET /tenants` is a genuine, permanent exception to the global filter. It is confined to
  one audited helper and covered by its own isolation test. This is accepted, not hidden.
- The route selector does not preclude later adding a convenience header or a session
  default — either would be an additional input to the same validated lookup, not a new
  trust path.

## Alternatives Considered

### `X-Tenant-Id` header

Identical trust properties, and equally sound if validated the same way. Rejected because
the tenant vanishes from the URL: it is easier to forget on a new endpoint, harder to see in
logs and traces before S4 exists, and awkward for cache keys — which the `security` skill
names as a place isolation breaks.

### Tenant identifier embedded in the access token

Superficially the strongest option, since the tenant would then be signed. Rejected on the
domain model: **our tenants are not Entra tenants.** A user's Entra `tid` says nothing about
which of our tenants they belong to, so the claim would have to be minted by us via a token
exchange, adding an issuer to operate and a re-auth step per tenant switch. It would also
couple our tenancy to Entra's, which `docs/architecture/domain-model.md` deliberately keeps
separate.

### Server-side "current tenant" session state

Rejected. Introduces server state to a service that has none, makes requests
context-dependent in a way FR-020's idempotency must then compensate for, and hides the
tenant from the request entirely — the opposite of the observability property that makes the
chosen option attractive.

### Trusting the route parameter without a membership lookup

Not seriously considered; recorded only because it is the failure this ADR exists to
prevent. It would make every tenant enumerable by identifier substitution — the canonical
IDOR vulnerability, and an existential one for this product per Principle IV.

## Revisit When

- The per-request membership lookup shows up as a measurable bottleneck. The answer is a
  better index or a very short-lived cache **with an explicit, documented authorization
  staleness window** — not removing the lookup.
- A cross-tenant *read* view is ever genuinely required (e.g. an operator console). That is a
  new decision, not an extension of this one, and ADR-013 already says so.
- Physical isolation per tenant arrives (ADR-013's most likely amendment). The selector
  survives; what changes is that it also selects a connection.

## Compliance

- Tenant resolution lives in **one** place — middleware or an equivalent single seam — never
  per endpoint. A tenant-scoped endpoint that resolves its own context is a defect.
- Every tenant-scoped operation has an isolation test asserting **both** refusal *and* that
  the response is indistinguishable from a non-existent tenant (spec 001 SC-004, zero
  exceptions).
- The three enumerated exceptions each have their own dedicated test.
- **Proposed for S3**: an architecture test asserting no endpoint reads `{tenantId}` other
  than through the resolution seam, alongside the raw-SQL and background-job gates that
  ADR-013 records as its known weakness ([U12](../traceability.md)).

## Note on ADR-013 and the `security` skill

This ADR **refines** ADR-013 rather than amending it; ADR-013's "never *trusted*" wording
already permits a validated selector.

The `security` skill previously phrased the rule as "Never from a route parameter, query
string, header, or body the caller controls" — stricter than the ADR and, read literally,
forbidding the design FR-010 requires. Per Principle II a skill cannot override an ADR, so
the skill was amended alongside this decision (2026-08-09) to distinguish a validated
*selector* from a trusted *grant*, and now points here. Corrected in the open rather than
tacitly ignored.
