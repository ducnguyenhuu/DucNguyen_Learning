# ADR-013: Shared infrastructure with logical tenant isolation

**Status**: Superseded by [ADR-025](ADR-025-single-organization.md) (2026-10-23)
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Principle IV · `idea.md` §19, §18 · roadmap S2 · `specs/001-auth-tenant-management` Assumption 2

## Context

The platform is multi-tenant SaaS holding customers' delivery and engineering data —
project status, team capacity, risk, release history. This is among the most
commercially sensitive data an engineering organisation has. A cross-tenant leak would
be an existential event for the product, not a bug to fix next sprint.

`idea.md` §19 requires isolation across eight surfaces: APIs, data, documents, vector
indexes, AI context, events, logs, and authorization. Note that four of those —
documents, vector indexes, AI context, events — do not exist yet. The isolation model
must therefore be one that extends to them, not one that only covers relational rows.

The immediate decision is forced by roadmap S2, which builds tenancy and persistence.

## Decision

We use **shared infrastructure with logical isolation**: one application deployment,
one database per service, and every tenant-scoped row carrying a tenant identifier.

Isolation is enforced by these means, in order of reliance:

1. **Query-level enforcement by default.** Tenant filtering is applied globally at the
   data-access layer, not written per query. A developer must not be able to omit it
   by forgetting.
2. **Tenant context resolved once per request** from the authenticated principal's
   membership, never from a client-supplied parameter that is trusted.
3. **Authorization evaluated against membership in the resolved tenant** for every
   tenant-scoped operation.
4. **Automated isolation tests** covering every tenant-scoped operation, treated as a
   release gate rather than as ordinary tests.

**Non-existence and inaccessibility are indistinguishable.** A tenant the caller
cannot access returns the same response as a tenant that does not exist, so tenant
existence cannot be probed.

**The rule extends to every surface as it arrives.** When documents, vector indexes,
AI context, and events are built, each must carry tenant scoping designed in, not
added. A vector index shared across tenants leaks exactly as effectively as a missing
SQL predicate and far less visibly.

Physical isolation — dedicated database or infrastructure per tenant — is **not**
implemented, and is deferred until a customer requires it contractually.

## Consequences

### Positive

- One deployment, one schema, one migration path. At the tens-of-tenants scale that
  Horizons 1–2 target, this is the difference between feasible and not.
- Cost scales sub-linearly with tenant count.
- Global query filtering means isolation holds by default rather than by developer
  vigilance — the only version of this that survives contact with a real codebase.
- Onboarding a tenant is a database row, not an infrastructure provisioning job.

### Negative

- **A single defect in the filtering layer is a cross-tenant breach.** This is the
  central risk of the decision and it is not mitigable by care alone; it is why item 4
  above is a release gate and why Principle IV requires tests for *every* operation
  rather than a representative sample.
- Any query written to bypass the global filter — raw SQL, a reporting view, a bulk
  export, a background job running without a request context — is a potential leak,
  and background jobs are the most likely place for this to happen.
- "Noisy neighbour" effects are possible: one tenant's large sync (roadmap S10) can
  degrade another's experience.
- Per-tenant data residency, per-tenant encryption keys, and per-tenant backup or
  restore are all effectively unavailable. Any of these being required by a customer
  triggers a revisit.

### Neutral / accepted trade-offs

- A user may belong to several tenants, but each request resolves to exactly one. No
  response ever spans tenants. Cross-tenant views, if ever needed, would be a new
  decision.
- Telemetry is tenant-annotated but shared (Principle VI). Log isolation per §19 is
  satisfied by annotation plus access control on the telemetry backend, not by
  separate log stores.
- The tenant identifier appears in essentially every tenant-scoped table. This is
  accepted redundancy.

## Alternatives Considered

### Database per tenant

Strongest isolation, and the easiest story to tell a security reviewer: a query
cannot cross a boundary that is a separate connection. Also enables per-tenant
residency, keys, backup, and restore.

Rejected for Horizons 1–2 on operational cost. Migrations must run across N databases,
connection management becomes stateful, onboarding becomes provisioning, and Azure SQL
cost scales linearly with tenants. For a solo developer at tens of tenants this
overwhelms the benefit. It remains the most likely future amendment, and the row-level
tenant identifier does not obstruct it.

### Schema per tenant

A middle option: one database, one schema per tenant. Stronger separation than row
filtering, cheaper than database-per-tenant.

Rejected because it combines the disadvantages more than the advantages: migrations
still multiply across schemas, tooling support is uneven in EF Core, and the isolation
gain over well-enforced global filtering is smaller than it appears — a background job
without tenant context can still address the wrong schema.

### Hybrid — shared by default, dedicated for enterprise tenants

The likely eventual answer, and explicitly what this ADR is designed not to obstruct.
Rejected *now* only because building both models before either has a customer is
speculative generality (Principle X). Deferred, not dismissed.

## Revisit When

- **A customer contractually requires physical isolation, data residency, or
  customer-managed encryption keys.** The most likely trigger, and it should be
  expected rather than treated as a surprise.
- Tenant count approaches roughly 500, where noisy-neighbour effects and blast radius
  both grow uncomfortable.
- Any cross-tenant leak occurs, or an isolation test catches one in development. Either
  is grounds to reopen this immediately rather than to patch and continue.

## Compliance

- **Global query filter** at the data-access layer, applied by default; its absence on
  a tenant-scoped entity is a defect, not a choice.
- **Automated isolation tests for every tenant-scoped operation** — spec 001 SC-004
  permits zero exceptions.
- **Gate 1** blocks Horizon 2 until cross-tenant access is proven refused across the
  board.
- **`idea.md` §59.2 safeguard:** multi-tenancy is not considered learned until an
  automated test has actually caught an attempted cross-tenant read. Write the test
  that fails first.

**Known weakness:** no automated gate currently prevents raw SQL or a background job
from bypassing the global filter. Closing this — an architecture test restricting raw
SQL execution outside audited helpers, and a requirement that background jobs resolve
tenant context explicitly — should be added in roadmap S3.
