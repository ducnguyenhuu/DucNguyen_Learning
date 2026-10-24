<!--
SYNC IMPACT REPORT — 1.0.1 → 2.0.0 (MAJOR)
==========================================
Date: 2026-10-23 · Approved by: project owner (chose "supersede and amend the
Constitution, removing Principle IV" when the change was scoped)

Reason: the project owner removed multi-tenancy (ADR-025). One deployment now serves
one organization, so Principle IV no longer describes anything the system does.
Removing a principle is a MAJOR change under step 4 of the Amendment Process.

Changed:
- Principle IV (Tenant Isolation) is RETIRED. Its heading is kept, marked retired
  with a pointer to ADR-025, so Principles V–XI keep their numbers and every existing
  "Principle VI" style reference stays valid.
- Principle VI: telemetry is annotated with user identity (not tenant and user);
  audit applies to security- and membership-significant events.
- Principle IX: AI spend is attributable to a caller, a capability and a cost.
- Quality Gates: the "Tenant isolation tests" gate is replaced by a "Membership
  tests" gate (non-members and non-administrators refused), enforcing V. The
  telemetry gate checks user identity, not tenant context.
- Mapping from idea.md §44 and the Technology Constraints ADR list updated
  (ADR-013 and ADR-017 superseded by ADR-025).
- Principle Gate Checklist: IV marked retired.

Deliberately NOT changed:
- Principle V's rule that responses must not disclose whether a resource exists.
  It is a general security rule, not a tenancy one.
- Other stale Technology Constraints (AKS, API Management). ADRs 023 and 024 changed
  those, which the section explicitly permits without an amendment.

Impact assessment (Amendment Process step 3):
- .specify/templates/*: ✅ no template names Principle IV.
- AGENTS.md, README.md, roadmap.md, docs/architecture/*, docs/traceability.md and
  the .agent/skills/* files: updated in the same change.
- specs/001–006: historical. Each spec.md carries a banner pointing to ADR-025;
  their bodies are not rewritten.
- ADR-013 and ADR-017: Superseded by ADR-025. ADR-022: point 4 refined. ADR-019:
  annotated.
-->

<!--
SYNC IMPACT REPORT — 1.0.0 → 1.0.1 (PATCH)
==========================================
Date: 2026-08-09 · Approved by: project owner

Reason: a factual error. Technology Constraints closed with "None exist yet" about
ADR-001, 002, 007, 011, 012, and 013 — all of which have existed since 2026-08-08.
The file therefore contradicted its own Follow-up TODOs below. Found during the
spec-001 post-planning consistency review.

Changed (Technology Constraints closing paragraph only):
- Replaced the stale "None exist yet" claim with a pointer to docs/adr/README.md as
  the authoritative index, plus the current ADR list including 003, 017, and 018.
- Added an explicit note that the constraint list is the current *default*, not
  immutable, and that an ADR may change a constraint without amending this document
  — which the top of that section already permitted but no reader would infer.
  ADR-018 (New Relic as telemetry backend) is named as the first such instance.

Deliberately NOT changed:
- The "Telemetry: OpenTelemetry" constraint. ADR-018 changed the telemetry *backend*,
  not the instrumentation standard. Naming a vendor here would recreate exactly the
  staleness this amendment fixes, and would force a constitution amendment every
  time a backend changes.
- No principle, rule, rationale, or Quality Gate. This is why it is a PATCH: nothing
  normative moved.

Impact assessment (Amendment Process step 3): none. No template, spec, plan, or
skill referenced the changed paragraph. docs/constitution.md is a pointer to this
file, not a copy (ADR-016), so it needs no edit.

Follow-up TODO status refreshed below to match reality.


SYNC IMPACT REPORT — initial ratification
=========================================
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
- README.md: ✅ Updated (2026-08-08) — states the project's purpose and links here.
- AGENTS.md: ✅ Created — condenses Principles I, II, IV, VIII for agent consumption.
- docs/constitution.md: ✅ Created as a pointer to this file, never a copy.
- specs/001-auth-tenant-management/spec.md: ✅ Compatible — verified against all
  11 principles; no conflicts. FR-027/FR-028 satisfy Principles III and VII,
  FR-007/FR-008/FR-009 satisfy Principle IV, FR-023..FR-026 satisfy Principle VI,
  and the spec's "no AI in slice one" stance satisfies Principle VIII.

Follow-up TODOs:
- ✅ RESOLVED (2026-08-08) TODO(ADR_BACKLOG): 10 ADRs written — 001, 002, 003, 007,
  008, 009, 011, 012, 013, 016 — plus framework and template at docs/adr/. Every
  Technology Constraint and Principles III, IV, VI, VIII, IX now have a recorded
  decision. ADRs 004, 005, 010, 014 are deliberately deferred with reasons in the
  index; 006 is folded into ADR-003; 015 is superseded by this document.
  **Updated 2026-08-09: twelve now exist.** Two were raised by work rather than
  pre-assigned, which is the expected pattern from here on:
    - ADR-017 (tenant context from a validated route selector) — raised by spec-001
      planning, because ADR-013 did not say how a user in several tenants selects
      one, and the `security` skill's wording forbade the only mechanism that
      satisfies FR-010. Skill amended alongside it.
    - ADR-018 (New Relic as the default telemetry backend) — refines ADR-011's
      backend clause; ADR-011's instrumentation decision is untouched. This is the
      first exception granted under ADR-001's "non-Azure services require an ADR".
- ✅ RESOLVED TODO(README).
- OPEN: **seven** decisions in docs/traceability.md require a human, not an agent
  (was six; U13 added 2026-08-09 for idea.md §17/§20 still naming Azure Monitor and
  Application Insights, which ADR-018 supersedes in practice — idea.md is higher
  authority than an ADR, so an agent proposes the blueprint amendment rather than
  making it). U6 is now partially resolved: performance testing assigned to S7.
  The most consequential remains U12 — no automated gate currently prevents a
  background job or raw SQL from bypassing the tenant filter, which is the likeliest
  route to a Principle IV violation. Assigned to roadmap S3.
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

### IV. (Retired) Tenant Isolation

**Retired in 2.0.0 (2026-10-23).** One deployment serves one organization
(ADR-025), so there are no tenants to isolate. The heading is kept so that
Principles V–XI keep their numbers.

If the platform ever serves more than one organization from one deployment, this
principle MUST be reinstated by amendment *before* the first tenant-scoped
change. Retrofitting isolation afterwards is exactly the failure it existed to
prevent.

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
- Telemetry MUST be annotated with user identity, and MUST NOT record
  unnecessary personal data or any secret.
- Every service MUST expose health status covering itself and each critical
  dependency.
- Every AI invocation MUST record token usage, cost, model, latency, and
  outcome.
- Security- and membership-significant events MUST produce immutable audit records
  capturing actor, subject, action, time, source, and outcome.
- A failure MUST be diagnosable from telemetry without local reproduction.

**Rationale:** This is a distributed, event-driven system where a
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
- Every AI invocation MUST be attributable to a caller, a capability, and a cost.
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
| 8. Secure-by-default | Principle V (tenancy was split into Principle IV, retired in 2.0.0) |
| 9. AI-provider abstraction | Principle IX |
| 10. Human approval for high-risk AI actions | Principle I |
| 11. Automated testing | Principle VII |
| 12. Architecture governance | Principle VII (authority order in Principle II) |
| 13. AI evaluation | Principle VIII |
| 14. Cost-aware AI usage | Principle IX |
| 15. System-level engineering metrics | Principle XI |

Two principles had no direct §44 counterpart and were promoted from elsewhere
in idea.md because they are non-negotiable and testable: **Principle IV** (tenant
isolation, from §19 — retired in 2.0.0 by ADR-025) and **Principle X** (vertical
slices, from §29 — idea.md calls it "a core development principle" but §44
omitted it).

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

Corresponding ADRs — the index at [docs/adr/](../../docs/adr/README.md) is
authoritative; this list is a convenience: ADR-001 (Azure), ADR-002 (.NET),
ADR-003 (service boundaries), ADR-007 (AKS), ADR-011 (OpenTelemetry),
ADR-012 (Terraform), ADR-018 (telemetry backend), ADR-025 (single organization;
supersedes ADR-013 and ADR-017).

**Read the list above as the current default, not as immutable.** A Technology
Constraint may be changed by an ADR without amending this document, per the note
at the top of this section. The first instance is ADR-018, which grants the
telemetry backend an exception to ADR-001's Azure-first rule.

## Quality Gates

All changes MUST pass these gates before merge. A gate that is not yet
implemented MUST be tracked as work, not treated as optional.

| Gate | Requirement | Enforces |
|------|-------------|----------|
| Build | No errors | — |
| Unit tests | All pass | VII |
| Integration tests | All pass | VII |
| Architecture tests | All pass; boundary violations fail the build | II, III, VII, IX |
| Membership tests | Every member-only route refuses non-members; every administrator-only route refuses Member and Reader | V |
| Secret scanning | No secret in source, image, or history | V |
| Vulnerability scan | No unresolved high or critical finding | V |
| Container image scan | No unresolved high or critical finding | V |
| Telemetry check | New request paths emit correlated traces with user identity | VI |
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
- [ ] IV — Retired (ADR-025); write "not applicable"
- [ ] V — No stored credentials or secrets; authorization enforced per request
- [ ] VI — Correlated telemetry, health, audit, and AI cost recording included
- [ ] VII — Automated gates cover the boundaries and behaviours this work touches
- [ ] VIII — Deterministic solution ruled out before any AI capability
- [ ] IX — AI consumed only through the abstraction; spend attributable
- [ ] X — Delivered as a working, tested, deployed, end-to-end slice
- [ ] XI — No individual-level measurement; personal data minimized

**Version**: 2.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-10-23
