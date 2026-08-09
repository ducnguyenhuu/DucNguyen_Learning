# ADR-003: Service-oriented architecture with exclusive data ownership

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Principle III · `idea.md` §14, §15, §44 items 3–5
**Supersedes the need for**: ADR-006 (data ownership) — see rationale below

## Context

The platform spans several genuinely distinct concerns: tenancy and identity,
integration with external engineering systems, delivery intelligence, and AI. These
differ in data ownership, scaling characteristics, external dependency risk, and
release cadence — an integration connector fails when Jira rate-limits it, which has
nothing to do with whether tenant management is healthy.

That argues for separation. But `idea.md` §14 also warns explicitly: *"We will not
create microservices merely because we can."* A solo developer building fifteen
slices cannot afford fifteen services, and premature decomposition would multiply
deployment, tracing, and consistency problems before any of them are real.

The decision must therefore settle both *how much* to decompose and, more
importantly, *what makes a boundary legitimate*.

## Decision

We use **service-oriented architecture organised around business capabilities**, not
microservices.

**A service boundary requires justification** by at least one of: bounded context,
distinct business ownership, distinct data ownership, security boundary, distinct
scaling characteristic, or distinct lifecycle. Technical possibility is not
justification.

**Each service owns its data store exclusively.** Cross-service database access is
prohibited without exception — no shared tables, no shared schemas, no read-only
replicas of another service's store. Services communicate only through published
APIs, events, or messaging.

**Within a service, Clean Architecture layering applies:** the domain layer depends
on nothing outward, and never on infrastructure.

The initial decomposition is deliberately small:

| Service | Owns | Justification |
|---------|------|---------------|
| Platform / Tenancy | tenants, users, memberships, invitations | security boundary; every other service depends on it |
| Integration | external connections, credentials, raw ingested data | distinct failure and scaling profile; external dependency risk |
| Delivery | canonical delivery data, health scores | bounded context; the product's core domain |
| AI Platform | prompts, invocations, costs, evaluations | distinct scaling and cost profile; provider abstraction seam |

Four services, introduced over Horizons 1–2 as their slices arrive — not up front.

### Why this absorbs ADR-006

`idea.md` §45 anticipated a separate ADR-006 for data ownership. It is folded in here
because the two are one decision expressed twice: **a service that does not own its
data is not a service boundary — it is a module with extra network latency.**
Recording them separately would let one drift from the other, which is precisely the
failure this ADR exists to prevent.

## Consequences

### Positive

- Independent deployment and scaling become genuinely possible, because no service
  can be coupled to another through a shared database — the failure mode that
  converts service-oriented systems into distributed monoliths.
- Integration failures are contained. A rate-limited connector cannot degrade
  tenancy.
- The AI Platform's provider seam (ADR-009) has somewhere to live that business
  logic cannot reach around.
- Boundaries are enforceable by automated test (Principle VII), so this ADR is not
  dependent on anyone remembering it.

### Negative

- **Cross-service queries become application-level joins.** Answering "which tenants
  have unhealthy projects" requires composing calls rather than one SQL statement.
  This is the real, recurring cost of the decision.
- Eventual consistency is now a permanent property of the system, not an edge case.
  Every cross-service invariant must tolerate staleness, and `idea.md` §21's list
  (idempotency, retries, duplicate delivery, correlation IDs) becomes mandatory work
  rather than good practice — which is why roadmap S8 exists.
- Four services means four deployment units, four sets of migrations, and four health
  surfaces before the product has a single customer.
- Local development requires more moving parts, which roadmap S5's compose setup must
  absorb.

### Neutral / accepted trade-offs

- Services may start as separately-bounded projects inside one deployable and split
  later. The **boundary** is the commitment; the process topology is not. What may
  never be deferred is the data ownership rule, because retrofitting it after a shared
  database exists is close to a rewrite.
- Four services is a starting point, not a target. Splitting further requires
  justification against the criteria above; so does merging.

## Alternatives Considered

### Modular monolith with a shared database

Genuinely attractive for a solo developer: one deployment, one database,
transactional consistency, no distributed-systems tax. It would remove most of
roadmap S8.

Rejected because the shared database is the part that cannot be undone. Module
boundaries in a monolith are enforceable and can be tightened later; a shared schema
that four capabilities have grown into cannot be separated without a migration
project. Since the research objective (`idea.md` §52) explicitly includes distributed
systems and service boundaries, deferring the hard part would also defer the
learning.

### Modular monolith with separate schemas per module

The strongest rejected option, and closest to a compromise: one deployable, but
exclusive data ownership preserved per module. It sacrifices independent scaling and
failure isolation while keeping the property that matters most.

Not adopted, but it remains **compatible with this ADR** — see the trade-off note
above. A service may legitimately begin life as a schema-isolated module in a shared
deployable. This ADR forbids shared data, not shared processes.

### Fine-grained microservices

One service per aggregate or per capability, as originally suggested by §5's product
domains. Rejected outright per `idea.md` §14. It would produce a dozen services
before the first customer, each with its own pipeline, telemetry, and failure modes,
and would make cross-cutting change nearly impossible for one person.

## Revisit When

- A service's data ownership boundary is repeatedly awkward — recurring
  application-level joins in the same place is evidence the boundary is wrong, and it
  should be moved rather than worked around (Principle II).
- A service needs materially different scaling than its deployable peers, which is
  the trigger to split process topology.
- Team size grows past the point where one person can hold all four services, which
  changes the ownership calculus.

## Compliance

Enforced automatically from roadmap S3:

- Architecture test: the domain layer has no dependency on infrastructure.
- Architecture test: no service references another service's data-access assembly,
  DbContext, or connection configuration.
- Architecture test: services reference each other only through published contract
  assemblies.
- A new service or a new database appears in Terraform (ADR-012) and is conspicuous
  in review.

A violation fails the build and cannot be merged (Principle VII).
