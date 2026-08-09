<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 → 1.0.0 (MAJOR — initial ratification for THIS project)

IMPORTANT — foreign content replaced: the file previously at this path was the
constitution of an unrelated TypeScript "tools-hub" project (token-reduction /
MCP-avoidance principles, npm workspaces, ESLint). It arrived via the `.specify`
bootstrap copy from ~/.specify during feature 001 setup and never applied to this
project. It has been discarded in full, not amended. Its stated "Version 1.0.0 |
Ratified 2026-01-21" belonged to that other project; this project's history
therefore starts at 1.0.0 today.

Modified principles: N/A (initial version for this project)

Added sections:
- Core Principles (11 principles)
- Technology Constraints
- Quality Gates
- Governance

Removed sections: all prior content (foreign project — see note above)

Source: derived from idea.md v0.5 §44 (15 numbered principles), plus §7, §14,
§15, §19, §20, §22, §24, §29, §42, §49, §56. The 15 source items are consolidated
into 11 principles; §44's items 1, 2, and 7 are technology decisions rather than
principles and move to Technology Constraints. A full mapping appears at the end
of Core Principles so nothing from §44 is silently dropped.

Templates requiring updates:
- .specify/templates/plan-template.md: ✅ Compatible — "Constitution Check" gate
  at line 30 is generic ("[Gates determined based on constitution file]") and now
  resolves against the Principle Gate Checklist below.
- .specify/templates/spec-template.md: ✅ Compatible — no changes needed;
  Principles IV, VI, and XI constrain spec content and are satisfied by the
  existing Requirements / Success Criteria structure.
- .specify/templates/tasks-template.md: ✅ Compatible — phase structure supports
  the observability, tenant-isolation, and architecture-test task types that
  Principles IV, VI, and VII require.
- .specify/templates/checklist-template.md: ✅ Compatible — no constitution
  references.
- .specify/templates/commands/: N/A — directory does not exist in this repo.
- README.md: ⚠ Pending — currently a single title line with no content. Should
  state the project's purpose and link to this constitution and idea.md.
- specs/001-auth-tenant-management/spec.md: ✅ Compatible — verified against all
  11 principles; no conflicts. FR-027/FR-028 satisfy Principles III and VII,
  FR-007/FR-008/FR-009 satisfy Principle IV, FR-023..FR-026 satisfy Principle VI,
  and the spec's "no AI in slice one" stance satisfies Principle VIII.

Follow-up TODOs:
- TODO(ADR_BACKLOG): Principles III, VIII, and IX assert positions that idea.md
  §45 expects to be recorded as ADR-003, ADR-008, and ADR-009. Those ADRs do not
  exist yet. Write them before /speckit.plan on feature 001, per idea.md §58.
- TODO(README): see ⚠ above.
-->

# Constitution: AI Engineering & Delivery Intelligence Platform

This constitution is the engineering law of this repository. It governs how the
platform is built, not what the platform does. Product direction lives in
`idea.md`; architectural decisions live in `docs/adr/`; this document sits above
both on matters of engineering conduct, per the hierarchy in idea.md §42.

## Core Principles

### I. Human Authority Over Intent, Architecture, and Risk

AI assists execution. Humans own intent, architecture, risk, and authorization.

**Rules:**

- A human MUST own and approve product vision, scope, priorities, architectural
  direction, risk acceptance, and production authorization.
- Deployment to production MUST require explicit human approval. No automated
  path to production may exist.
- AI-initiated actions that mutate customer data, external systems, spend money,
  or affect production MUST require human approval before execution.
- An AI agent MUST NOT expand the scope of work beyond what its task specifies.
  If the work appears to require more, it MUST stop and ask.
- Work products MUST be reported faithfully. A failing test, a skipped step, or
  an unverified assumption MUST be stated plainly, never presented as complete.

**Rationale:** This project's premise is that AI agents can participate in
engineering safely and economically. "Safely" is doing the work here: an agent
with unbounded authority is not a research result, it is an incident waiting to
happen. Constraining agent authority is what makes the research legitimate rather
than reckless — and this is the principle whose violation is hardest to detect
after the fact, which is why it is first.

### II. Architectural Authority Is Hierarchical

When guidance conflicts, the higher authority wins, and disagreement is raised
rather than resolved unilaterally.

**Rules:**

- The authority order MUST be: product direction → product specification → this
  constitution → architecture → ADRs → feature specification → implementation
  plan → code and tests → agent skills.
- A skill MUST NOT override an ADR, a specification, or this constitution. Where
  a skill conflicts with an ADR, the ADR wins.
- On discovering that an ADR, specification, or architectural decision appears
  wrong, the discoverer MUST stop and propose a change. Silently redesigning
  around it is prohibited.
- Every architecturally significant decision MUST be recorded as an ADR before
  or alongside the code implementing it, never afterward as archaeology.
- Tasks MUST be treated as implementation guidance, not a blind to-do list. The
  implementer MUST inspect the existing code, check relevant ADRs, and verify
  assumptions before proceeding.

**Rationale:** With multiple agents and multiple context sources, conflicting
instructions are inevitable rather than exceptional. Without a declared
precedence order, conflicts resolve by whichever instruction happened to be in
context — a silent, unauditable failure mode. The "propose, don't override" rule
is what keeps architectural drift visible.

### III. Business-Capability Boundaries with Explicit Data Ownership

Services are organized around business capabilities, and each owns its data
exclusively.

**Rules:**

- Service boundaries MUST be justified by bounded context, business ownership,
  data ownership, security boundary, scaling characteristic, or lifecycle. A new
  service MUST NOT be created merely because it is technically possible.
- Each service MUST own its data store exclusively. Cross-service database
  access is prohibited without exception.
- Services MUST communicate only through published APIs, events, or messaging.
- The domain layer MUST NOT depend on infrastructure.
- An entity MUST NOT be duplicated from a source system it is merely mirroring.
  Native entities are justified only where the platform adds something the
  source system lacks.

**Rationale:** Shared databases are the most common way service-oriented
architectures collapse into a distributed monolith — the coupling is invisible
in the code and only surfaces when independent deployment becomes impossible.
The final rule guards a failure specific to this product: idea.md §3 commits to
being an intelligence layer over Jira and Azure DevOps, and the fastest way to
betray that is to gradually reimplement them.

### IV. Tenant Isolation Is Non-Negotiable

Every tenant-scoped operation resolves to exactly one tenant, and cross-tenant
access is impossible rather than merely unlikely.

**Rules:**

- Every request MUST resolve to exactly one active tenant context. A request
  whose tenant context is absent, malformed, or not one the caller belongs to
  MUST be rejected, never defaulted.
- No response may ever contain data belonging to a tenant the caller is not a
  member of.
- A tenant the caller cannot access MUST be indistinguishable from a tenant that
  does not exist, so tenant existence cannot be probed.
- Isolation MUST hold across APIs, data, documents, vector indexes, AI context,
  events, logs, and authorization — not data alone.
- Every tenant-scoped capability MUST have automated tests proving cross-tenant
  access is refused. Isolation MUST NOT rest on developer discipline.

**Rationale:** This is a multi-tenant SaaS platform holding customers'
engineering and delivery data — among the most commercially sensitive data an
organisation has. A single cross-tenant leak is an existential event for the
product, not a bug to be fixed in the next release. The explicit inclusion of
vector indexes and AI context matters because those are where isolation is most
often forgotten: an embedding index or a prompt context assembled across tenants
leaks just as effectively as a missing SQL predicate, and far less visibly.

### V. Secure by Default

Security is a property of the default path, not an added layer.

**Rules:**

- Authentication MUST be delegated to the corporate identity provider. The
  platform MUST NOT store or manage user passwords.
- Service-to-service and service-to-infrastructure authentication MUST use
  workload identity. Stored credentials, connection strings with secrets, and
  long-lived keys are prohibited.
- Secrets MUST NOT appear in source control, container images, logs, telemetry,
  or error messages. They MUST be retrieved at runtime from managed secret
  storage.
- Authorization MUST be enforced on every request. Unauthenticated and
  unauthorized MUST be distinguishable to the caller but MUST NOT disclose
  whether a resource exists.
- Access MUST follow least privilege, and errors MUST NOT disclose internal
  detail.

**Rationale:** Security added after the fact is security that does not hold.
Every rule here is cheap when it is the default and expensive to retrofit — a
secret committed once must be treated as compromised forever, and a service
built on connection strings does not become a managed-identity service without
touching every deployment path.

### VI. Observable by Default

A change is not complete until its behaviour in production is diagnosable from
telemetry alone.

**Rules:**

- Every request MUST emit logs, metrics, and traces correlated by a single
  identifier spanning the entire request path, across process and messaging
  boundaries.
- Telemetry MUST be annotated with tenant and user identity, and MUST NOT record
  unnecessary personal data or any secret.
- Every service MUST expose health status covering itself and each critical
  dependency.
- Every AI invocation MUST record token usage, cost, model, latency, and
  outcome.
- Security- and tenancy-significant events MUST produce immutable audit records
  capturing actor, subject, action, time, source, and outcome.
- A failure MUST be diagnosable from telemetry without local reproduction.

**Rationale:** This is a distributed, event-driven, multi-tenant system where a
single user action crosses an API, a service, a message bus, an agent, a search
index, and a model. Without correlated traces spanning that path, production
debugging degrades into guesswork. The last rule is the testable form of this
principle: if reproducing the bug locally is the only way to understand it, the
instrumentation is inadequate.

### VII. Automated Gates, Not Reviewer Vigilance

Anything that must always be true MUST be enforced by a gate that fails the
build. Human review does not scale and does not remember.

**Rules:**

- Architectural boundaries MUST be enforced by automated architecture tests. At
  minimum: the domain layer cannot depend on infrastructure; no service may
  access another service's data store; AI requests must route through the AI
  abstraction.
- A change violating an architectural boundary MUST fail the build and MUST NOT
  be mergeable.
- Every functional requirement MUST have automated test coverage.
- The pipeline MUST gate on build, unit tests, integration tests, architecture
  tests, vulnerability scanning, and container image scanning.
- Distributed-system behaviour MUST be explicitly handled and tested: timeout,
  retry, idempotency, circuit breaking, dead-lettering, duplicate delivery,
  eventual consistency, and correlation ID propagation.
- A rule that cannot be automatically enforced SHOULD be reconsidered or made
  enforceable, because unenforced rules decay.

**Rationale:** Every principle above is worthless if compliance depends on
someone noticing during review. Architecture tests convert architectural intent
from documentation into an executable constraint — which is what makes the
"architecture governance" claim in idea.md §52 a research result rather than an
aspiration. The explicit distributed-systems list exists because those failures
are invisible in local development and appear only under production concurrency.

### VIII. Deterministic First — AI Must Earn Its Place

AI is used where it creates measurable value, not where it is available.

**Rules:**

- Before any AI capability is built, it MUST be established that deterministic
  logic cannot solve the problem. Where deterministic logic can solve it,
  deterministic logic MUST be used.
- Where AI is justified, it MUST be evaluated on quality, cost, latency,
  security, grounding, and observability before adoption.
- Scoring, thresholds, and computable classifications MUST be deterministic. AI
  MAY explain, narrate, and recommend over those results.
- AI output consumed programmatically MUST be structured, validated, and safe to
  reject.
- AI responses presented as fact MUST be grounded in retrievable data, and the
  grounding MUST be inspectable.
- Model choice MUST be decided by measurement, not preference. Self-hosted
  inference MUST NOT be assumed cheaper than managed models without comparing
  quality, GPU cost, utilization, latency, operational cost, security, and
  availability.

**Rationale:** "LLM everywhere" produces systems that are slower, costlier,
non-reproducible, and impossible to test. The scoring rule is the sharpest
application: whether a project is at risk is arithmetic over metrics and must be
reproducible and auditable, whereas *why* it is at risk is genuine reasoning over
context. Putting AI on the correct side of that line is most of what separates a
useful product from a demo.

### IX. AI Provider Abstraction and Cost Accountability

Business logic never couples to a model provider, and AI spend is always
attributable.

**Rules:**

- Business services MUST consume AI only through the platform's AI abstraction.
  Direct calls to a model provider from business logic are prohibited and MUST
  be blocked by an architecture test.
- Callers MUST request capabilities, not named models. Model selection is the
  abstraction's responsibility.
- Every AI invocation MUST be attributable to a tenant, a capability, and a cost.
- Gateway capability MUST NOT be built before a named consumer requires it. The
  abstraction seam exists from the start; the machinery behind it grows on
  demand.

**Rationale:** Model providers, prices, and capabilities change faster than this
platform's release cycle; a provider name embedded in business logic becomes a
migration project. The final rule guards the opposite error, and is the one most
likely to be violated by enthusiasm: idea.md §9 lists eleven gateway
responsibilities, and building a router with one route is the speculative
generality that Principle III's first rule already prohibits for services.

### X. Vertical Slices Deliver Working Software

Work is delivered as small, end-to-end capabilities, never as large incomplete
technical layers.

**Rules:**

- Each slice MUST produce working, tested, deployable software exercising the
  full path from entry point to persistence to telemetry.
- A slice MUST NOT be considered complete until it is tested, observable, and
  deployed to a real environment.
- Horizontal layers spanning many months without a deployment are prohibited.
- Infrastructure required by a slice MUST be defined as code and reproducible
  into a clean environment with no manual configuration.
- A slice MUST NOT build capability for anticipated future needs. Where a future
  need is foreseen, the seam is created and the implementation deferred.

**Rationale:** Vertical slices surface wrong assumptions in weeks rather than
months, keep the system continuously deployable, and bound the context an agent
must hold — which directly improves the quality of AI-assisted work. The
"tested, observable, deployed" bar exists because the alternative definition of
done, where the code is written but nothing runs, is how large speculative
implementations get justified.

### XI. Measure Systems, Never Rank Individuals

The platform measures engineering systems. It does not evaluate people.

**Rules:**

- Metrics MUST describe systems, teams, and processes. The platform MUST NOT
  produce individual developer productivity rankings, scores, or comparisons.
- No feature may be built whose primary purpose is evaluating an individual's
  performance.
- Where a metric could be misused to evaluate an individual, it MUST be
  aggregated or withheld.
- Personal data in telemetry and AI context MUST be minimized to what the
  capability genuinely requires.

**Rationale:** Individual productivity metrics are both ethically corrosive and
technically invalid: they measure what is countable rather than what is
valuable, and they reliably cause people to optimize the metric at the expense
of the work. This principle is stated as engineering law rather than product
preference because the pressure to add such a feature will come from buyers, and
a principle that yields to commercial pressure is not a principle.

### Mapping from idea.md §44

All fifteen items in idea.md §44 are accounted for. None were dropped.

| §44 item | Where it lives now |
|----------|--------------------|
| 1. Azure-first | Technology Constraints |
| 2. .NET-first | Technology Constraints |
| 3. Business-capability-oriented services | Principle III |
| 4. Explicit data ownership | Principle III |
| 5. API/event-based service communication | Principle III |
| 6. Observable-by-default | Principle VI |
| 7. Terraform-managed infrastructure | Technology Constraints + Principle X |
| 8. Secure-by-default | Principle V (tenancy split into Principle IV) |
| 9. AI-provider abstraction | Principle IX |
| 10. Human approval for high-risk AI actions | Principle I |
| 11. Automated testing | Principle VII |
| 12. Architecture governance | Principle VII (authority order in Principle II) |
| 13. AI evaluation | Principle VIII |
| 14. Cost-aware AI usage | Principle IX |
| 15. System-level engineering metrics | Principle XI |

Two principles have no direct §44 counterpart and were promoted from elsewhere
in idea.md because they are non-negotiable and testable: **Principle IV** (tenant
isolation, from §19 — too important to remain a sub-clause of secure-by-default)
and **Principle X** (vertical slices, from §29 — idea.md calls it "a core
development principle" but §44 omitted it).

## Technology Constraints

These are decisions, not principles. They may change through the ADR process
without amending this constitution.

- **Cloud**: Azure-first. Non-Azure services require an ADR.
- **Language / Runtime**: .NET, C#, ASP.NET Core.
- **Orchestration**: Containers on AKS, fronted by Azure API Management and
  Azure Front Door.
- **Data**: Azure SQL, per-service ownership (Principle III).
- **Messaging**: Azure Service Bus as the default asynchronous mechanism.
- **Identity**: Microsoft Entra ID with managed identity.
- **Secrets**: Azure Key Vault, accessed by workload identity.
- **Infrastructure**: Terraform. Manual portal configuration is prohibited —
  infrastructure MUST be reproducible into an empty subscription from code alone.
- **Telemetry**: OpenTelemetry as the common instrumentation.
- **Design approach**: Domain-Driven Design, Clean Architecture, SOLID,
  dependency inversion, REST for synchronous APIs, event-driven where
  asynchrony is genuinely warranted.

Corresponding ADRs: idea.md §45 expects ADR-001 (Azure), ADR-002 (.NET),
ADR-007 (AKS), ADR-011 (OpenTelemetry), ADR-012 (Terraform), ADR-013
(multi-tenancy). None exist yet — see the deferred TODOs above.

## Quality Gates

All changes MUST pass these gates before merge. A gate that is not yet
implemented MUST be tracked as work, not treated as optional.

| Gate | Requirement | Enforces |
|------|-------------|----------|
| Build | No errors | — |
| Unit tests | All pass | VII |
| Integration tests | All pass | VII |
| Architecture tests | All pass; boundary violations fail the build | II, III, VII, IX |
| Tenant isolation tests | Cross-tenant access refused for every tenant-scoped operation | IV |
| Secret scanning | No secret in source, image, or history | V |
| Vulnerability scan | No unresolved high or critical finding | V |
| Container image scan | No unresolved high or critical finding | V |
| Telemetry check | New request paths emit correlated traces with tenant context | VI |
| Requirement coverage | Every functional requirement has a test | VII |
| Human approval | Required for production deployment | I |

## Governance

### Precedence

This constitution supersedes skills, plans, tasks, and code conventions. It is
subordinate to product direction and product specification on questions of what
to build, and it governs how the work is done. Where an ADR conflicts with this
constitution, this constitution wins and the ADR MUST be revised.

### Amendment Process

1. Propose the change as a pull request to this file, stating the rationale and
   which principle or constraint it affects.
2. A human maintainer MUST approve. An AI agent MUST NOT amend this file
   unilaterally; it may only propose.
3. Assess impact on dependent artifacts: plan, spec, tasks, and checklist
   templates, ADRs, and agent skills.
4. Increment the version:
   - **MAJOR**: a principle is removed, or redefined incompatibly.
   - **MINOR**: a principle is added, or existing guidance materially expanded.
   - **PATCH**: clarification, wording, or non-semantic refinement.
5. Update the Last Amended date and the Sync Impact Report at the top of this
   file.

### Compliance Review

- Every pull request MUST verify compliance with these principles.
- Complexity or deviation beyond these constraints MUST be justified explicitly
  in the pull request, not assumed acceptable.
- Where a principle is repeatedly deviated from, the correct response is to amend
  the principle or build the missing gate — not to normalize the deviation.

### Principle Gate Checklist

`/speckit.plan` resolves its "Constitution Check" gate against this list. A plan
MUST state, for each principle, either how it complies or why the principle does
not apply.

- [ ] I — Human approval retained for production and for high-risk AI actions
- [ ] II — Relevant ADRs identified; conflicts proposed rather than worked around
- [ ] III — Service and data boundaries respected; no cross-service data access
- [ ] IV — Tenant isolation enforced and tested for every tenant-scoped operation
- [ ] V — No stored credentials or secrets; authorization enforced per request
- [ ] VI — Correlated telemetry, health, audit, and AI cost recording included
- [ ] VII — Automated gates cover the boundaries and behaviours this work touches
- [ ] VIII — Deterministic solution ruled out before any AI capability
- [ ] IX — AI consumed only through the abstraction; spend attributable
- [ ] X — Delivered as a working, tested, deployed, end-to-end slice
- [ ] XI — No individual-level measurement; personal data minimized

**Version**: 1.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-08
