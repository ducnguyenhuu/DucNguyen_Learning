# Architecture Decision Records

An ADR records **one architecturally significant decision**: what was decided, why,
what it costs, and what was rejected. It is written when the decision is made, not
reconstructed afterward.

## Why ADRs have teeth here

Constitution **Principle II** places ADRs above feature specs, plans, code, and
agent skills in the authority hierarchy. Two consequences:

- **A skill or plan that conflicts with an ADR loses.** The ADR wins.
- **If an ADR appears wrong, propose a change — do not work around it.** Silently
  redesigning around an ADR is prohibited for humans and agents alike.

An ADR may be superseded, never quietly edited into a different decision. Supersede
by writing a new ADR that references the old one and setting the old one's status to
`Superseded by ADR-NNN`.

## Status values

| Status | Meaning |
|--------|---------|
| `Proposed` | Written, not yet accepted. Not yet authoritative. |
| `Accepted` | Authoritative. Binding on all work. |
| `Superseded by ADR-NNN` | No longer binding. Retained for the historical record. |
| `Deprecated` | No longer relevant; nothing replaced it. |

## Writing one

Copy [`adr-template.md`](adr-template.md). Keep it short — one page is normal, three
is suspicious. The **Consequences** and **Alternatives Considered** sections are the
ones with long-term value; a decision recorded without its cost and its rejected
options is barely recorded at all.

Number allocation follows `idea.md` §45, which pre-assigns ADR-001 through ADR-015.
Numbers above 015 are allocated as needed — 016 onward were raised by the work rather
than pre-assigned, which is the expected pattern from here on.

**Refinement over rewriting.** Where a later decision changes part of an earlier one
(018 changes 011's backend but not its instrumentation rule), the earlier ADR is
annotated in place and marked *refined*, not deleted or silently edited. The history of
what was decided and why it changed is the point of the record.

## Index

| ADR | Title | Status | Enforces |
|-----|-------|--------|----------|
| [001](ADR-001-azure-first.md) | Azure as the primary cloud | Accepted | Constraints |
| [002](ADR-002-dotnet-first.md) | .NET and C# as the primary stack | Accepted | Constraints |
| [003](ADR-003-service-oriented-architecture.md) | Service-oriented architecture over microservices | Accepted | Principle III |
| 004 | Service boundaries | *Not yet written* — needs the domain model (roadmap S1) |  |
| 005 | Azure Service Bus | *Not yet written* — decision belongs to roadmap S8 |  |
| 006 | Data ownership | Folded into ADR-003 and Principle III; see note below |  |
| [007](ADR-007-aks-in-horizon-1.md) | AKS in Horizon 1, not deferred | Accepted | Constraints |
| [008](ADR-008-ai-gateway-staged.md) | AI Gateway built in stages, seam first | Accepted | Principle IX |
| [009](ADR-009-capability-based-model-abstraction.md) | Capability-based model abstraction | Accepted | Principle IX |
| 010 | RAG | *Not yet written* — Horizon 3, Track B |  |
| [011](ADR-011-opentelemetry.md) | OpenTelemetry as the instrumentation standard | Accepted — backend clause refined by 018 | Principle VI |
| [012](ADR-012-terraform.md) | Terraform for all infrastructure | Accepted | Constraints |
| [013](ADR-013-multi-tenancy-model.md) | Shared infrastructure with logical tenant isolation | Accepted | Principle IV |
| 014 | AI governance | *Not yet written* — Horizon 2, alongside roadmap S13–S15 |  |
| 015 | AI-assisted development methodology | Superseded in advance by the Constitution, which is the operative document |  |
| [016](ADR-016-agent-neutral-skill-location.md) | Agent-neutral skill location | Accepted | idea.md §38 |
| [017](ADR-017-tenant-context-resolution.md) | Tenant context from a validated route selector | Accepted | Principle IV |
| [018](ADR-018-new-relic-telemetry-backend.md) | New Relic as the default telemetry backend | Accepted | Principle VI |
| [019](ADR-019-single-entra-tenant-in-horizon-1.md) | One Entra tenant in Horizon 1; multi-directory sign-in deferred | Accepted | Principle IV, X |
| [020](ADR-020-ef-core-rowversion-pinning-requires-explicit-modified-state.md) | Pinning a RowVersion for optimistic concurrency requires explicit EntityState.Modified | Accepted | FR-021 |
| [021](ADR-021-application-layer-patterns-at-first-consumer.md) | Application-layer pattern machinery adopted at its first real consumer | Proposed | Principle IX, X |

### Deliberately unwritten

ADRs 004, 005, 010, and 014 are **not** oversights. Writing them now would mean
recording decisions before the information needed to make them exists — which is the
speculative generality Principle III and ADR-008 both reject. Each is scheduled:

- **004 Service boundaries** — needs the domain model and bounded contexts (roadmap S1).
- **005 Azure Service Bus** — the messaging decision is made in roadmap S8. The
  Constitution already names Service Bus as the default; the ADR records the
  trade-offs once real messaging patterns exist.
- **010 RAG** — Horizon 3 Track B. No consumer yet.
- **014 AI governance** — Horizon 2. Governance rules written before the first AI
  capability exists would be guesses.

**006 Data ownership** is folded into ADR-003 rather than split out, because the
service-boundary decision and the data-ownership rule are one decision expressed two
ways: a service that does not own its data is not a service boundary. Splitting them
would invite the two to drift.

**015 AI-assisted development methodology** is not written as an ADR because the
Constitution *is* that decision, at higher authority. An ADR restating it would
create two sources of truth for the same rule, and Principle II exists precisely to
prevent that.
