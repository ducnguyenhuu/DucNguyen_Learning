# Roadmap

**Read page 1 only.** Everything after the line marked `REFERENCE` is detail you open
when you start a slice — not reading material.

---

# ▶ PAGE 1 — START HERE

## The whole project is 15 pieces of work, done one at a time

### Foundation — 8 pieces (~3–4 months)

| # | Work | Done when |
|---|------|-----------|
| 1 | Constitution + ADRs | Architecture decisions written down |
| 2 | Login + tenant + database | Works on your machine |
| 3 | Architecture tests | Breaking a boundary fails the build |
| 4 | Logging + tracing | You can find a failure without reproducing it |
| 5 | Docker | `docker compose up` runs everything |
| 6 | Terraform + Azure | It runs in the cloud |
| 7 | CI/CD | Commit deploys itself |
| 8 | Service Bus | Duplicate messages don't break it |

**→ GATE 1:** Can you deploy to Azure in under 20 minutes with no manual step?
**If no — do not start piece 9.**

### Real data + AI — 7 pieces (~3 months)

| # | Work | Done when |
|---|------|-----------|
| 9 | Connect Jira (read-only) | Real data is in the system |
| 10 | Sync engine | Survives rate limits and mid-sync failure |
| 11 | Normalize the data | Queryable, and you know how fresh it is |
| 12 | Project health score | **No AI** — plain arithmetic |
| 13 | AI abstraction layer | All AI goes through one door |
| 14 | AI answers "why is my project yellow?" | The product's core value |
| 15 | Measure AI quality | You have numbers to defend it |

**→ GATE 2:** Does a real Delivery Manager say *"yes — and I didn't know that"*?
If they say *"I already knew that"*, the product idea is wrong. Fix it before continuing.

### After that

Undecided, on purpose. Piece 14 tells you what to build next.

---

## Where you are right now

```text
  1  Constitution + ADRs               DONE
       Constitution v1.0.0 · 10 ADRs + framework
       Repo skeleton · AGENTS.md · 7 skills · domain model
▶ 2  Login + tenant + database         NEXT — spec ready
  3  Architecture tests                not started
```

**This week:** run `/speckit.plan` on piece 2, then `/speckit.tasks`, then write code.

Six open decisions sit in [docs/traceability.md](docs/traceability.md#open-decisions).
None blocks piece 2.

---

## How this maps to idea.md

Same plan, different words. idea.md calls them *Phases*; here they are numbered pieces
of work.

| idea.md | = pieces |
|---------|----------|
| Phase 0 + 1 — Foundation | 1–8 |
| Phase 2 — Integration | 9–11 |
| Phase 3 — AI Gateway | 13 |
| Phase 5 — Delivery Intelligence | 12, 14, 15 |
| Phase 4, 6, 7 | Undecided (after Gate 2) |

Below, each piece is called a **slice** (idea.md §29's word) and numbered **S1–S15**.
The two groups are called **Horizons** because each ends in a gate that can be failed.

## The other files

Open these only when you need them. None is reading material.

| File | When to open it |
|------|-----------------|
| [idea.md](idea.md) | The vision and the why. Your document. |
| [docs/adr/](docs/adr/) | "Why did we choose this?" |
| [docs/traceability.md](docs/traceability.md) | "Did we forget anything from idea.md?" — 6 open decisions |
| [specs/001-*](specs/001-auth-tenant-management/spec.md) | Piece 2's requirements |
| [Constitution](.specify/memory/constitution.md) | The 11 rules all work must follow |

---
---

# REFERENCE

Detail for each slice. **Open the one you are starting; skip the rest.**

Each slice states four things:

| Field | Purpose |
|-------|---------|
| **Scope** | What is in. If it is not listed, it is not in the slice. |
| **Not in scope** | What will feel tempting and must be deferred. This field is the point. |
| **Outcome** | What becomes true. An observable fact, not an activity. |
| **Proof** | How you know it is done. Cannot check every box → not done. |

**Research targets** appear because this project is research-first (idea.md §59.2): a
slice is not complete until its technology has been driven under *failure* conditions,
not just demonstrated working.

**Working assumption:** full-time, 1–2 weeks per slice.

---

# HORIZON 1 — Enterprise Foundation

**8 slices · ~13–16 weeks**

*Objective: a real person authenticates against something you deployed to Azure
through a pipeline, and you can explain its behaviour from telemetry alone.*

---

## S1 — Engineering System Foundation

**~1–1.5 weeks** · No dependencies

Establishes the architectural authority everything else must cite. No product code.

**Scope**
- Engineering constitution — **done**, v1.0.0, 11 principles
- ADR framework + template at `docs/adr/`
- ADR-001 Azure-first · ADR-002 .NET-first · ADR-003 Service-oriented architecture
- ADR-007 AKS in Horizon 1 (record *why* it was not deferred — idea.md §59.2)
- ADR-008 AI Gateway staged, seam-first · ADR-009 Capability-based model abstraction
- Repository skeleton: `src/ tests/ infrastructure/ deployment/ docs/ specs/ .agent/`
- `AGENTS.md` + the 7 initial skills (idea.md §55 Step 8) — no more
- Domain model and bounded contexts at `docs/architecture/domain-model.md`, which must
  classify all 14 of `idea.md` §6's delivery concepts as projection / native / not-in-MVP
  ([traceability U8](docs/traceability.md#u8--6s-14-delivery-entities-vs-46as-projections-not-native-entities))
- Resolve the six open decisions in [docs/traceability.md](docs/traceability.md#open-decisions)

**Not in scope**
- Any application code · any Azure resource · the remaining ADRs 004–006, 010–015
  (write them when the decision is actually being made, not speculatively)
- More than 7 skills

**Outcome**
Every Technology Constraint in the constitution has a corresponding ADR, and the
Principle Gate Checklist can be evaluated against something real.

**Proof**
- [ ] `/speckit.plan` on any feature can cite an ADR for each technology it uses
- [ ] Constitution's Principle Gate Checklist is answerable for all 11 principles
- [ ] Domain model names the bounded contexts and their data ownership
- [ ] `docs/constitution.md` is a pointer to `.specify/memory/constitution.md`, not a copy

**Research targets:** spec-driven development, ADR practice, skill scoping.

---

## S2 — Auth + Tenant + Persistence (local)

**~2–3 weeks** · Depends on S1

The first real code. Runs and is fully verifiable on your machine.

**Scope**
- Microsoft Entra ID authentication; no password handling
- Tenant create / read / update; membership; invitations; roles (Admin/Member/Reader)
- Tenant isolation enforced in the data access path
- Domain model + clean architecture layering (domain has no infrastructure dependency)
- EF Core, migrations, Azure SQL running in a local container
- Unit tests + integration tests against a real database
- Basic structured logging and no-secrets-in-source hygiene (spec 001 FR-025, FR-026)

**Spec:** [`specs/001-auth-tenant-management/`](specs/001-auth-tenant-management/spec.md)
— 26 functional requirements, 9 success criteria, 3 user stories.

**Not in scope**
- Azure deployment · containerization of the app itself · OpenTelemetry
- Service Bus · any UI beyond what proves the acceptance scenarios
- Tenant deletion or data export

**Outcome**
A real person signs in with a corporate account, creates an isolated tenant,
invites a colleague, and cross-tenant access is provably impossible — all
verifiable locally.

**Proof**
- [ ] All 15 acceptance scenarios across Stories 1–3 pass
- [ ] Automated test proves cross-tenant read is refused for every tenant-scoped operation
- [ ] A tenant you cannot access is indistinguishable from one that does not exist
- [ ] Last-administrator removal is refused
- [ ] Migrations apply to an empty database and the app starts clean
- [ ] Repository history contains no secret (scan history, not just working tree)

**Research targets:** DDD, clean architecture, Entra ID integration, EF Core,
multi-tenant isolation patterns.

---

## S3 — Architecture Tests + Test Pyramid

**~1 week** · Depends on S2

Converts architectural intent into an executable constraint. Do this *early* —
retrofitting boundaries after violations accumulate is far more expensive.

**Scope**
- Test project structure: `UnitTests / IntegrationTests / ContractTests / ArchitectureTests`
- Architecture tests: domain cannot depend on infrastructure; no cross-service data
  access; layering respected; AI calls must route through the abstraction (assert
  the rule now, even though the seam arrives in S13)
- **Close the four enforcement gaps the ADRs acknowledge**
  ([traceability U12](docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs)) —
  most importantly, a test preventing raw SQL or a background job from bypassing the
  tenant filter, which is the likeliest route to a cross-tenant leak under ADR-013
- Test data builders and fixtures
- All suites runnable by one command and CI-ready

**Not in scope**
- End-to-end, performance, or security test suites · mutation testing

**Outcome**
An architectural boundary violation fails the build rather than relying on someone
noticing in review.

**Proof**
- [ ] A deliberately introduced domain→infrastructure reference fails the build
- [ ] A deliberate cross-service data access attempt fails the build
- [ ] Every functional requirement in spec 001 maps to at least one test
- [ ] Full suite runs unattended in under 5 minutes

**Research targets:** NetArchTest / ArchUnitNET, automated architecture governance
(idea.md §52's stated research goal).

---

## S4 — Observability

**~1.5–2 weeks** · Depends on S2

**Scope**
- OpenTelemetry: traces, metrics, logs
- Correlation ID generated at entry and propagated across every boundary
- Trace enrichment with tenant and user identity — no secrets, minimal personal data
- Health checks: self + each critical dependency
- Immutable audit log: actor, subject, action, time, source, outcome
- Structured logging conventions
- Local telemetry backend (.NET Aspire dashboard or Jaeger) for verification

**Not in scope**
- Azure Monitor / Application Insights wiring — that arrives with S6
- Dashboards, alerting, SLOs

**Outcome**
A failure is diagnosable from telemetry alone, without reproducing it locally.

**Proof**
- [ ] One tenant operation produces a single correlated trace from entry to database
- [ ] A deliberately induced failure is diagnosed from telemetry in under 10 minutes,
      with no local reproduction
- [ ] Health endpoint correctly reports a stopped database as unhealthy
- [ ] Audit entries exist for authentication, tenant mutation, and authorization refusal
- [ ] No secret and no unnecessary personal data appears anywhere in telemetry

**Research targets:** OpenTelemetry, correlation across async boundaries, audit design.

---

## S5 — Containerization

**~1 week** · Depends on S4

**Scope**
- Multi-stage Dockerfile; non-root user; minimal base image
- `docker-compose` bringing up app + SQL + telemetry collector
- Container health check; graceful shutdown; startup time and image size tuned
- Local configuration and secret handling that does not bake secrets into the image

**Not in scope**
- AKS, Helm, Kubernetes manifests — those are S6
- Multi-architecture builds

**Outcome**
The entire stack runs from a single command on a clean machine.

**Proof**
- [ ] `docker compose up` on a clean checkout yields a working, signed-in-able app
- [ ] Image contains no secret (verified by scanning the built image, not the Dockerfile)
- [ ] Container runs as non-root and responds correctly to SIGTERM
- [ ] Image size and cold start recorded as a baseline to compare against later

**Research targets:** container hardening, .NET container image optimization.

---

## S6 — Terraform → Azure

**~3–4 weeks** · Depends on S5 · **The expensive slice**

This is the largest single slice in the roadmap and the main cost of the
research-first orientation (idea.md §59.2). Budget for it honestly.

**Scope**
- Terraform with remote state; one `dev` environment
- Resource group · Azure Container Registry · AKS · API Management · Front Door
- Azure SQL · Key Vault · Log Analytics + Application Insights
- Managed identity and workload identity federation — no stored credentials
- Private endpoints and network isolation
- Kubernetes manifests / Helm chart for the app
- First deployment, performed manually to learn the path

**Not in scope**
- Pipeline automation of this deployment — that is S7 and must stay separate
- Service Bus — S8 · Production or QA environments · Autoscaling, multi-region
- **Azure AI Search** — listed in `idea.md` §17 but has no consumer until Horizon 3
  Track B. Provisioning it here would pay for an idle service for months and violates
  Principle X. See [traceability U2](docs/traceability.md#u2--17-provisions-ai-search-which-nothing-uses-until-horizon-3).

**Outcome**
The whole environment provisions into an empty Azure subscription from code alone,
and the application is reachable and healthy in Azure.

**Proof**
- [ ] `terraform apply` into an *empty* subscription produces a working environment
      with zero manual portal configuration
- [ ] App is reachable through Front Door → APIM → AKS and passes health checks
- [ ] Application authenticates to SQL and Key Vault via managed identity, with no
      connection-string secret anywhere
- [ ] Traces from the Azure-deployed app appear in Application Insights, correlated
- [ ] **A rollout is deliberately broken and recovered** (research-first safeguard —
      AKS is not learned until this has happened)
- [ ] `terraform destroy` cleanly removes everything

**Cost warning:** roughly $700–1,500/month at standard SKUs. Use dev/test SKUs,
and `terraform destroy` between working sessions — the fact that this is safe to do
is itself part of Proof item 1.

**Research targets:** Terraform, AKS, APIM, private networking, managed identity,
workload identity federation. This slice is where most of the enterprise-stack
learning actually happens.

---

## S7 — CI/CD

**~1.5–2 weeks** · Depends on S6

**Scope**
- Pipeline: build → unit → integration → architecture tests → secret scan →
  dependency vulnerability scan → container build → image scan → push to ACR → deploy dev
- Conventional-commit validation (per repository CLAUDE.md)
- Branch protection; required checks
- A human approval gate standing between dev and any higher environment

**Not in scope**
- Production environment or deployment · AI evaluation in the pipeline (S15)
- Blue/green or canary strategies

**Outcome**
A commit reaches the dev environment in under 20 minutes with no manual step, and
cannot reach production without a human.

**Proof**
- [ ] Commit → dev deploy in under 20 minutes, fully unattended
- [ ] A change violating an architectural boundary is rejected by the pipeline
- [ ] A planted test secret is caught by secret scanning
- [ ] A known-vulnerable dependency fails the build
- [ ] Production deployment is impossible without explicit human approval
- [ ] A non-conforming commit message fails the build

**Research targets:** GitHub Actions, supply-chain scanning, deployment gating.

---

## S8 — Service Bus + Distributed-Systems Behaviour

**~2 weeks** · Depends on S7

The research-first payoff slice. One event is enough — the point is the failure
handling around it, not the number of events.

**Scope**
- Azure Service Bus provisioned via Terraform
- One real event end to end: `TenantCreated`
- Publisher using the outbox pattern (no dual-write)
- Subscriber with idempotent handling backed by a deduplication store
- Retry with exponential backoff; circuit breaker
- Dead-letter queue plus tooling to inspect and replay
- Correlation ID propagated *through* the message, so the trace stays unbroken

**Not in scope**
- Additional events · sagas or orchestration · event sourcing · schema registry

**Outcome**
The platform handles asynchronous messaging correctly under duplicate delivery and
failure, demonstrated rather than assumed.

**Proof**
- [ ] `TenantCreated` flows publisher → Service Bus → subscriber
- [ ] **A deliberately duplicated message is handled idempotently** — no double effect
- [ ] **A message is dead-lettered and successfully replayed** using your own tooling
- [ ] A distributed trace spans HTTP entry → publish → Service Bus → subscriber → database
- [ ] Outbox guarantees the event is not lost when the publish fails after commit
- [ ] Circuit breaker opens under sustained downstream failure and recovers

**Research targets:** Azure Service Bus, idempotency, the outbox pattern, dead-letter
operations, eventual consistency. This is what idea.md §21's distributed-systems
list looks like when it is real.

---

# ⛔ GATE 1

**Do not begin Horizon 2 until every box is checked.** Everything after this point
assumes the foundation holds; building on an unproven one multiplies problems
rather than adding them.

- [ ] A change reaches Azure through the pipeline in under 20 minutes, no manual step
- [ ] A deliberately induced failure is diagnosed from telemetry alone in under 10 minutes
- [ ] Cross-tenant access is refused for every tenant-scoped operation, proven by tests
- [ ] A duplicated Service Bus message is handled idempotently, demonstrated
- [ ] A dead-lettered message has been replayed, demonstrated
- [ ] An architectural boundary violation fails the build
- [ ] The whole environment provisions into an empty subscription from code alone
- [ ] An AKS rollout has failed and been recovered
- [ ] No secret exists in source control, container images, logs, or telemetry

---

# HORIZON 2 — Real Data and First AI

**7 slices · ~14 weeks**

*Objective: a real Delivery Manager connects their real Jira or Azure DevOps
project and learns something they did not already know.*

---

## S9 — Integration Service + One Connector

**~2–3 weeks** · Depends on Gate 1

**Scope**
- `Integration.Service` with its own database (Principle III — exclusive ownership)
- A connector abstraction, and exactly **one** implementation: Jira **or** Azure
  DevOps. Pick one and commit.
- Per-tenant credential capture and storage in Key Vault
- Read-only fetch: projects, work items, sprints/iterations, status history
- Raw landing store — persist what the API returned, before any transformation

**Not in scope**
- Write-back to the source system · a second connector · transformation or
  normalization (S11) · webhooks · scheduling (S10)

**Outcome**
A tenant connects their real Jira or Azure DevOps project and their actual data
lands in the platform.

**Proof**
- [ ] A real project — ideally your own team's — is connected and fetched
- [ ] Credentials are stored per tenant in Key Vault and never logged
- [ ] Raw responses are persisted and re-readable without re-fetching
- [ ] Tenant A cannot see tenant B's connection or ingested data
- [ ] You have written down what surprised you about the real data

That last item is not filler. It is the finding that shapes S11 and S12, and it is
the reason integration comes before native entities (idea.md §57.2).

**Research targets:** integration patterns, tenant-scoped external credentials,
real-world API behaviour.

---

## S10 — Sync Engine + Failure Handling

**~2 weeks** · Depends on S9

**Scope**
- Scheduled background sync
- Incremental / delta sync — do not refetch everything
- Rate-limit detection with backoff and resumption
- Auth expiry detection and a clear re-authentication path for the tenant
- Partial-failure recovery — a sync that dies halfway resumes correctly
- Idempotent upsert; sync status and history visible per tenant

**Not in scope**
- Real-time webhooks · multi-connector orchestration · backfill of years of history

**Outcome**
Sync survives the ways real external APIs actually fail, demonstrated rather than
hoped.

**Proof**
- [ ] **A rate-limit response is handled with backoff and the sync completes**
- [ ] **An expired credential is detected and surfaced, not silently swallowed**
- [ ] **A sync killed halfway resumes without duplicating or losing data**
- [ ] Incremental sync measurably transfers less than a full sync
- [ ] Sync failures are visible in telemetry with the tenant and cause identified

**Research targets:** hostile real-world APIs, sync idempotency, resumable jobs.

---

## S11 — Delivery Data Model + Freshness

**~2 weeks** · Depends on S10

**Scope**
- Canonical ingested model: project, work item, sprint, status transition history
- Mapping from connector-specific shapes to canonical
- Data freshness surfaced to the user — when was this last synced
- Data-quality signals: missing estimates, unused fields, abandoned workflows
- **Projections over ingested data — not native duplicated entities**

**Not in scope**
- Native `Project` / `Team` / `Release` / `Milestone` aggregates. The MVP reaches
  its exit criterion without them (idea.md §46a). Do not build a Jira clone.

**Outcome**
Normalized, queryable delivery data with known freshness and, critically, known gaps.

**Proof**
- [ ] Canonical model populated from the real connected project
- [ ] Freshness is visible for every ingested entity
- [ ] Data-quality gaps are reported rather than silently defaulted
- [ ] Status transition history is complete enough to compute trends over time
- [ ] No entity duplicates a source-system field without adding something

**Research targets:** canonical modelling over messy heterogeneous sources.

---

## S12 — Deterministic Project Health Score

**~2 weeks** · Depends on S11 · **No AI in this slice**

The most underrated slice in the roadmap. Principle VIII applied: the score is
arithmetic, reproducible, and auditable. AI explains it later — it does not compute it.

**Scope**
- Health scoring over ingested data: scope change rate, velocity trend, blocked
  item age, sprint completion trend, due-date slip
- Per-factor contribution breakdown — not just a colour
- Configurable thresholds
- Backtest against historical data: would this have flagged projects that actually slipped?

**Not in scope**
- Any LLM · machine-learning forecasting · recommendations

**Outcome**
"Project = Yellow" comes with an auditable, reproducible arithmetic reason.

**Proof**
- [ ] The same inputs always produce the same score
- [ ] Every score decomposes into named contributing factors with weights
- [ ] Backtested against real history, it flags projects that genuinely slipped
- [ ] **A delivery manager looks at the factor breakdown and agrees it is measuring
      the right things** — before any AI is involved
- [ ] Score computation is covered by tests using real historical fixtures

**Research targets:** metric design, distinguishing signal from noise in real
delivery data.

---

## S13 — AI Seam + Provider + Cost Accounting

**~2 weeks** · Depends on S12

Stage 1 of the gateway only (idea.md §9a). The seam is permanent; the machinery
behind it is minimal.

**Scope**
- Capability-based AI abstraction — callers request `ReleaseRiskAnalysis`, not a model name
- Exactly **one** provider implementation (Azure OpenAI)
- Prompt management with versioning
- Token counting; cost attribution per tenant and per capability
- AI telemetry: model, latency, tokens, cost, outcome
- Structured output contract with validation and safe rejection
- Architecture test forbidding any direct provider call from business logic

**Not in scope**
- Model routing · a second provider · RAG · policies · rate limits · tool calling ·
  agent runtime. None of these have a consumer yet (Principle IX).

**Outcome**
AI is callable through a seam, and every invocation is attributable and costed.

**Proof**
- [ ] A capability request returns validated structured output
- [ ] A direct provider call from business logic fails the architecture test
- [ ] Every invocation records tenant, capability, model, tokens, cost, latency
- [ ] **Malformed model output is rejected safely rather than propagated**
- [ ] Cost per invocation is queryable per tenant

**Research targets:** provider abstraction, structured LLM output, token economics.

---

## S14 — First AI Capability: Risk Narrative

**~2 weeks** · Depends on S13 · **The MVP's core value**

**Scope**
- Answer "why is my project yellow?" grounded in S12's score and S11's data
- Structured output: contributing factors, evidence, forecast, recommended actions
- Inspectable grounding — every claim traceable to ingested data
- Explicit refusal when the data is insufficient, rather than confabulating
- No scoring inside the model (Principle VIII)

**Not in scope**
- Actions that mutate anything · multi-turn conversation · agents · write-back to Jira

**Outcome**
The product's core value proposition works end to end on real customer data.

**Proof**
- [ ] Explanation generated for the real connected project
- [ ] Every factual claim is traceable to specific ingested data
- [ ] With deliberately insufficient data, the system declines rather than invents
- [ ] The narrative does not contradict S12's deterministic score
- [ ] Cost and latency per explanation are recorded and acceptable

**Research targets:** grounding, structured reasoning prompts, hallucination control.

---

## S15 — AI Evaluation Harness

**~2 weeks** · Depends on S14

**Scope**
- Evaluation dataset built from real projects with known outcomes
- Quality dimensions: grounded, accurate, useful, non-contradictory
- Automated scoring with regression detection between prompt versions
- Cost and latency tracked per evaluation run
- Evaluation runnable in CI

**Not in scope**
- A full evaluation platform · large-scale human labelling · A/B testing in production

**Outcome**
You can defend the AI's quality with numbers rather than impressions.

**Proof**
- [ ] Evaluation suite runs unattended and produces a score
- [ ] A deliberately worsened prompt is caught as a regression
- [ ] Ungrounded claims are detected automatically
- [ ] Cost per insight is known and defensible
- [ ] Evaluation runs in the pipeline

**Research targets:** AI evaluation methodology — one of idea.md §52's explicit goals.

---

# ⛔ GATE 2 — The Falsification Test

This gate is designed to be **failed**. Failing it here is the most valuable
outcome the roadmap can produce, because everything in Horizon 3 rests on it.

- [ ] A real Delivery Manager, shown a real risk explanation about **their own**
      project, says **"yes — and I didn't know that."**
- [ ] Cost per insight is known and defensible
- [ ] The evaluation harness produces a quality score you would show someone else
- [ ] Every AI response is grounded in retrievable data, inspectably

**If they say "I already knew that"** → the insight is real but not valuable. The
scoring in S12 or the data in S11 is too shallow. Iterate there; do not proceed.

**If they say "that's wrong"** → grounding or data quality has failed. Return to
S11/S14 before building anything on top.

**If they say "yes, and I didn't know that"** → the premise holds. Choose Horizon 3
tracks based on what they asked for *next*.

---

# HORIZON 3 — Research Tracks

**Pick at most two.** Running all five returns this project to a 24-month plan with
no decision points. Choose based on what Gate 2 actually revealed.

Deliberately low detail: scoping these now would be guessing, and the whole point
of Gate 2 is that it changes the answer.

| Track | Scope sketch | Outcome | Est. |
|-------|-------------|---------|------|
| **A — Model Economics** | Second provider · model routing · capability-based selection · self-hosted Llama vs managed comparison across quality, GPU cost, utilization, latency, ops cost (idea.md §11) | Model choice is decided by measurement, not preference | 5–6 slices, ~10–12 wks |
| **B — Knowledge & RAG** | Ingestion · document processing · embeddings · hybrid + vector search · grounded responses · **tenant-isolated vector indexes** (Principle IV) | AI grounded in documents, not only structured data | 6 slices, ~12–14 wks |
| **C — Agentic Platform** | Tool calling · agent orchestration · human approval workflows · event-triggered agents · controlled automation | Agents act, with humans authorizing anything consequential | 6–7 slices, ~14 wks |
| **D — Engineering Intelligence** | Second connector (GitHub) · engineering metrics · capacity · technical debt · reliability · architecture health — **system-level only, never individual ranking** (Principle XI) | A second persona (Engineering Manager) is served | 7 slices, ~14 wks |
| **E — Product B: The Engineering System** | Multi-agent workflows · agent verification · automated architecture governance · methodology measurement (idea.md §57.5) | The methodology that builds the platform becomes measurable | 5 slices, ~10 wks |

**Note on Track E:** idea.md §57.5 records that Product B still has no success
measure. A candidate is *the proportion of merged changes that passed spec → plan →
tasks → implementation without a human rewriting the agent's output.* Do not fix a
target for it until Horizons 1–2 have produced real data.

---

## Summary

| | Slices | Duration | Cumulative |
|---|---|---|---|
| Horizon 1 — Enterprise Foundation | S1–S8 | ~13–16 wks | ~4 months |
| **⛔ Gate 1** | | | |
| Horizon 2 — Real Data & First AI | S9–S15 | ~14 wks | ~7 months |
| **⛔ Gate 2** | | | |
| Horizon 3 — two chosen tracks | ~10–13 | ~20–26 wks | ~12–13 months |

Horizons 1 and 2 — **15 slices, ~7 months** — are the entire committed plan.
Everything past Gate 2 is deliberately undecided.

---

## Next action

Finish **S1**: write the ADR framework and ADR-001, 002, 003, 007, 008, 009. The
constitution's Principle Gate Checklist cannot be evaluated against ADRs that do
not exist, and `/speckit.plan` on S2 will need to cite them.

Then narrow spec 001 to Stories 1–3 before planning it.
