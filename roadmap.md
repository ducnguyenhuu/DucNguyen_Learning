# Roadmap

15 slices, done one at a time. Two gates. Everything past Gate 2 is undecided on purpose.

**Vocabulary:** *slice* = one piece of working software (idea.md §29) · *gate* = a check
that can be **failed**, where you stop and reconsider.

Full reasoning in [idea.md §46](idea.md) · rules in the
[Constitution](.specify/memory/constitution.md) · decisions in [docs/adr/](docs/adr/).

---

## Progress

| # | Slice | Status | Est. |
|---|-------|--------|------|
| **S1** | Constitution + ADRs + foundation | ✅ **done** | — |
| **S2** | Auth + tenant + persistence (local) | ✅ **done** — [spec](specs/001-auth-tenant-management/spec.md) | 2–3 w |
| **S3** | Architecture tests | ✅ **done** — [spec](specs/002-architecture-tests/spec.md) | 1 w |
| **S4** | Observability | ✅ **done** — [spec](specs/003-observability/spec.md) | 1.5–2 w |
| **S5** | Containerization | ✅ **done** — [spec](specs/004-containerization/spec.md) | 1 w |
| S6 | Terraform → Azure | ⬜ | **3–4 w** |
| S7 | CI/CD | ⬜ | 1.5–2 w |
| S8 | Service Bus | ⬜ | 2 w |
| | **⛔ GATE 1** | | |
| S9 | Integration + one connector | ⬜ | 2–3 w |
| S10 | Sync engine | ⬜ | 2 w |
| S11 | Delivery data model | ⬜ | 2 w |
| S12 | Health score (no AI) | ⬜ | 2 w |
| S13 | AI seam + cost tracking | ⬜ | 2 w |
| S14 | AI risk narrative | ⬜ | 2 w |
| S15 | AI evaluation | ⬜ | 2 w |
| | **⛔ GATE 2** | | |

**~7 months full-time.** Mark a slice ✅ only when every *Done when* box is checked.

### → Next steps

1. ✅ `/speckit.plan` — done 2026-08-09. Produced
   [plan](specs/001-auth-tenant-management/plan.md),
   [research](specs/001-auth-tenant-management/research.md),
   [data model](specs/001-auth-tenant-management/data-model.md),
   [contracts](specs/001-auth-tenant-management/contracts/openapi.yaml),
   [quickstart](specs/001-auth-tenant-management/quickstart.md), and
   [ADR-017](docs/adr/ADR-017-tenant-context-resolution.md) (Accepted)
2. ✅ Create the Entra app registrations ([quickstart](specs/001-auth-tenant-management/quickstart.md) §1)
   — done 2026-08-15, verified with a real access token against the running API
3. ✅ `/speckit.tasks` — done, 97 tasks
4. ✅ Implement S2, checking off its *Done when* list — done 2026-08-15
5. Optional: merge this branch to `main` — constitution and ADRs are project-level, not
   feature-level
6. ✅ Implement S3, checking off its *Done when* list — done 2026-08-17
7. ✅ Implement S4, checking off its *Done when* list — done 2026-08-25
8. ✅ Implement S5, checking off its *Done when* list — done 2026-09-25

Open decisions in [docs/traceability.md](docs/traceability.md#open-decisions). None blocks
S2. **U12 must be done in S3.** U6's performance gap was closed into S7 during S2 planning.

---

## How to read a slice

**Build** = what is in · **Not** = what to defer (this line is the point) ·
**Done when** = the checklist.

This project is research-first (idea.md §59.2), so several checks are **failure
scenarios**, not features. A technology demonstrated only on the happy path teaches you
the least useful thing about it.

---

# FOUNDATION — Horizon 1

*Goal: a real person logs into something you deployed to Azure, and you can explain its
behaviour from telemetry alone.*

## S1 — Constitution + ADRs + foundation ✅

**Built:** Constitution v1.0.0 (11 principles) · 10 ADRs + framework · repo skeleton ·
`.gitignore` · `AGENTS.md` · 7 skills · [domain model](docs/architecture/domain-model.md) ·
[traceability audit](docs/traceability.md)

---

## S2 — Auth + tenant + persistence · 2–3 w

Runs and is verifiable **on your machine**. No Azure needed.

**Build:** Entra ID auth · tenant CRUD · membership · invitations · 3 roles · tenant
isolation in the data layer · clean architecture layering · EF Core + migrations · SQL in
a container · unit + integration tests

**Not:** Azure · containerizing the app (S5) · OpenTelemetry (S4) · Service Bus (S8) ·
UI beyond what proves the scenarios

**Done when**
- [x] All 15 acceptance scenarios in [spec 001](specs/001-auth-tenant-management/spec.md) pass
- [x] **A test proves cross-tenant read is refused — for every tenant-scoped operation**
- [x] An inaccessible tenant is indistinguishable from one that does not exist
- [x] Removing the last administrator is refused
- [x] Migrations apply to an empty database; app starts clean
- [x] No secret in git history (scan history, not just the working tree)

---

## S3 — Architecture tests · 1 w

Do this early. Retrofitting boundaries after violations accumulate is far more expensive.

**Build:** test projects (Unit / Integration / Contract / Architecture) · domain ≠
infrastructure · no cross-service data access · no provider SDK outside AI Platform ·
**raw SQL restricted to audited helpers** · **background jobs must set tenant context**
([U12](docs/traceability.md#u12--enforcement-gaps-acknowledged-in-the-adrs))

**Not:** E2E · performance · security test suites (all post-Gate-1)

**Done when**
- [x] **A deliberate domain→infrastructure reference fails the build**
- [x] **A deliberate cross-service data access fails the build**
- [x] Every FR in spec 001 maps to a test
- [x] Full suite runs unattended in under 5 minutes

---

## S4 — Observability ✅ · 1.5–2 w

Backend is **New Relic** over OTLP ([ADR-018](docs/adr/ADR-018-new-relic-telemetry-backend.md)).
Its free tier means this slice runs against a **real** backend with no Azure subscription —
ADR-011 had assumed a local collector until S6, so this is a gain.

**Build:** OpenTelemetry traces/metrics/logs · OTel Collector exporting to New Relic ·
correlation ID propagated across every boundary · tenant + user enrichment **on spans and logs
only** · health checks (self + dependencies) · immutable audit log · sampling / drop rules ·
local collector for offline work

**Not:** App Insights as secondary exporter (S6, optional) · dashboards · alerting · SLOs ·
New Relic APM agent — **ever** (ADR-011, ADR-018: OTLP only, no vendor SDK)

**Done when**
- [x] One operation = one correlated trace, entry → database, **visible in New Relic**
- [x] **An induced failure is diagnosed from telemetry alone in under 10 min, no local repro**
- [x] Health reports a stopped database as unhealthy
- [x] Audit entries exist for auth, tenant mutation, and authorization refusal
- [x] No secret and no unnecessary personal data anywhere in telemetry
- [x] **`tenant.id` appears on spans and logs but on no metric dimension** — New Relic's
      cardinality limit is per metric, per day, and this is cheap now and costly to unpick later
- [x] **`NrIntegrationError` is empty** — OTLP validation is asynchronous, so a 2xx does not
      mean the data was accepted. A backend that silently discards part of your telemetry is
      worse than one that rejects it
- [x] Sampling or drop rules in place — the free tier **stops ingest** at 100 GB/month rather
      than billing over, so a log flood costs days of observability

---

## S5 — Containerization ✅ · 1 w

**Build:** multi-stage Dockerfile, non-root, minimal base · `docker compose` with app +
SQL + collector · health check · graceful shutdown · image size and startup baseline

**Not:** Azure Container Apps · Terraform · registry push (all S6)

**Done when**
- [x] `docker compose up` on a clean checkout gives a working, signed-in-able app
- [x] **Scanning the built image finds no secret** (scan the image, not the Dockerfile)
- [x] Runs as non-root; handles SIGTERM correctly
- [x] Image size and cold start recorded as a baseline

---

## S6 — Terraform → Azure · 3–4 w ⚠️ the expensive one

The main cost of going research-first ([ADR-007](docs/adr/ADR-007-aks-in-horizon-1.md)).
Compute is **Azure Container Apps, not AKS** ([ADR-023](docs/adr/ADR-023-azure-container-apps-for-compute.md),
2026-10-16). The old **~$700–1,500/month** estimate assumed AKS; re-estimate when the S6 plan is revised —
APIM, Front Door, and private endpoints now dominate. Use dev/test SKUs and `terraform destroy` between sessions.

**Open, deliberately deferred to this slice (2026-08-09): which subscription funds it.**
Candidates are the existing sandbox and Azure for Students (~$100 credit, no card). Note that
$100 does not cover this footprint — it reduces the bill, it does not solve it. Deciding at S6
rather than now avoids burning credit four slices before it is needed. The Entra tenant used
for authentication is a **separate** choice and is already settled: a subscription in one
tenant can serve an app registered in another.

**Build:** Terraform + remote state · one `dev` environment · ACR · Container Apps · APIM · Front
Door · Azure SQL · Key Vault (**holds the New Relic ingest licence key**) · OTel Collector as a
Container Apps sidecar · user-assigned managed identity · private endpoints · first deploy done by
hand, to learn the path

**Not:** pipeline automation (S7) · Service Bus (S8) · QA or production ·
**Azure AI Search** — no consumer until after Gate 2
([U2](docs/traceability.md#u2--17-provisions-ai-search-which-nothing-uses-until-horizon-3)) ·
**Log Analytics + App Insights** — the telemetry backend is New Relic
([ADR-018](docs/adr/ADR-018-new-relic-telemetry-backend.md)); App Insights is an optional
second collector exporter, and only if something needs it

**Done when**
- [ ] `terraform apply` into an **empty** subscription works — zero portal clicks
- [ ] App reachable through Front Door → APIM → Container Apps, health passing
- [ ] SQL and Key Vault reached by managed identity — **no connection-string secret**
- [ ] Traces from Azure appear in **New Relic**, correlated, with the licence key read from
      Key Vault by managed identity — never from a manifest
- [ ] **A revision is deliberately broken and recovered** — a bad revision fails its probes, takes no
      traffic, and traffic is shifted back. Container Apps is not learned until this
- [ ] `terraform destroy` removes everything cleanly

*Expect friction: APIM takes 30–45 min per apply; private endpoint + DNS wiring is where
the unknown-unknowns live.*

---

## S7 — CI/CD · 1.5–2 w

**Build:** build → unit → integration → architecture → secret scan → dependency scan →
container build → image scan → push ACR → deploy dev · conventional-commit validation ·
branch protection · human approval gate before anything above dev · **a load test against
the deployed dev environment** ([U6](docs/traceability.md#u6--22-lists-eight-test-types-only-four-are-scheduled))

**Not:** production environment · AI evaluation in the pipeline (S15) · blue/green

**Done when**
- [ ] Commit → dev in under 20 minutes, fully unattended
- [ ] **A change violating an architectural boundary is rejected by the pipeline**
- [ ] **A planted test secret is caught by secret scanning**
- [ ] **A known-vulnerable dependency fails the build**
- [ ] Production is impossible without explicit human approval
- [ ] A non-conforming commit message fails the build
- [ ] **Spec 001 SC-003 verified** — 95% of tenant reads under 1s at 50 concurrent users
      across 20 tenants. Deferred here from S2 because this is the first slice with both a
      pipeline to run the test and a real environment to run it against.

---

## S8 — Service Bus · 2 w

One event is enough. The point is the failure handling around it, not the count.

**Build:** Service Bus via Terraform · `TenantCreated` end to end · publisher using the
**outbox pattern** (no dual-write) · idempotent subscriber with a dedupe store · retry
with backoff · circuit breaker · DLQ + your own replay tooling · correlation ID carried
*through* the message

**Not:** more events · sagas · event sourcing · schema registry

**Done when**
- [ ] `TenantCreated` flows publisher → Service Bus → subscriber
- [ ] **A duplicated message is handled idempotently — no double effect**
- [ ] **A dead-lettered message is replayed using your own tooling**
- [ ] One trace spans HTTP → publish → Service Bus → subscriber → database
- [ ] The outbox proves the event survives a publish failure after commit
- [ ] Circuit breaker opens under sustained failure, then recovers

---

# ⛔ GATE 1

**Do not start S9 until every box is checked.** Building on an unproven foundation
multiplies problems rather than adding them.

- [ ] A change reaches Azure through the pipeline in under 20 min, no manual step
- [ ] An induced failure is diagnosed from telemetry alone in under 10 min
- [ ] Cross-tenant access is refused for every tenant-scoped operation, proven by tests
- [ ] A duplicate Service Bus message was handled idempotently
- [ ] A dead-lettered message was replayed
- [ ] An architectural boundary violation fails the build
- [ ] The environment provisions into an empty subscription from code alone
- [ ] A Container Apps revision has failed and been recovered
- [ ] No secret in source, images, logs, or telemetry

---

# REAL DATA + AI — Horizon 2

*Goal: a real Delivery Manager connects their real Jira and learns something they did not
already know.*

## S9 — Integration + one connector · 2–3 w

**Build:** `Integration.Service` with its own database · connector abstraction · **one**
connector (Jira **or** ADO — pick one) · per-tenant credentials in Key Vault · read-only
fetch of projects, work items, sprints, status history · raw landing store

**Not:** write-back · a second connector · normalization (S11) · scheduling (S10) · webhooks

**Done when**
- [ ] A real project — ideally your own team's — is connected and fetched
- [ ] Credentials stored per tenant in Key Vault, never logged
- [ ] Raw responses persisted and re-readable without re-fetching
- [ ] Tenant A cannot see tenant B's connection or data
- [ ] **You have written down what surprised you about the real data**

*That last item is not filler — it is the finding that shapes S11 and S12, and it is why
integration comes before native entities (idea.md §57.2).*

---

## S10 — Sync engine · 2 w

**Build:** scheduled sync · incremental/delta · rate-limit backoff and resumption · auth
expiry detection + re-auth path · partial-failure recovery · idempotent upsert · sync
status and history per tenant

**Not:** real-time webhooks · multi-connector orchestration · deep historical backfill

**Done when**
- [ ] **A rate-limit response is handled with backoff and the sync completes**
- [ ] **An expired credential is surfaced, not silently swallowed**
- [ ] **A sync killed halfway resumes without duplicating or losing data**
- [ ] Incremental sync measurably transfers less than a full sync
- [ ] Sync failures visible in telemetry with tenant and cause

---

## S11 — Delivery data model · 2 w

**Build:** canonical model (project, work item, sprint, status history) · connector
mapping · freshness surfaced per entity · data-quality signals (missing estimates, unused
fields) · **projections, not native entities**

**Not:** native `Project` / `Team` / `Release` / `Milestone` aggregates. Only **Risk**,
**HealthScore**, **Insight** are native in the MVP — see
[domain model](docs/architecture/domain-model.md). Do not build a Jira clone (idea.md §3).

**Done when**
- [ ] Canonical model populated from the real connected project
- [ ] Freshness visible for every ingested entity
- [ ] Data-quality gaps reported, not silently defaulted
- [ ] Status history complete enough to compute trends over time
- [ ] No entity duplicates a source field without adding something

---

## S12 — Health score · 2 w · **no AI**

The most underrated slice. Principle VIII: the score is arithmetic, reproducible, and
auditable. AI explains it later — it does not compute it.

**Build:** scoring over ingested data (scope change, velocity trend, blocked-item age,
sprint completion, due-date slip) · per-factor contribution breakdown · configurable
thresholds · **backtest against real history**

**Not:** any LLM · ML forecasting · recommendations

**Done when**
- [ ] Same inputs always produce the same score
- [ ] Every score decomposes into named factors with weights
- [ ] Backtested against real history, it flags projects that genuinely slipped
- [ ] **A delivery manager sees the factor breakdown and agrees it measures the right
      things — before any AI is involved**
- [ ] Covered by tests using real historical fixtures

---

## S13 — AI seam + cost tracking · 2 w

Stage 1 only ([ADR-008](docs/adr/ADR-008-ai-gateway-staged.md)). The seam is permanent;
the machinery behind it is minimal.

**Build:** capability-based abstraction (callers ask for `ReleaseRiskAnalysis`, not a
model name) · **one** provider · versioned prompts · token counting · cost per tenant and
capability · AI telemetry · structured output contract + validation · architecture test
banning direct provider calls

**Not:** routing · a second provider · RAG · policies · rate limits · tool calling ·
agent runtime. **None has a consumer yet** (Principle IX).

**Done when**
- [ ] A capability request returns validated structured output
- [ ] **A direct provider call from business logic fails the architecture test**
- [ ] Every invocation records tenant, capability, model, tokens, cost, latency
- [ ] **Malformed model output is rejected safely, not propagated**
- [ ] Cost per invocation is queryable per tenant

---

## S14 — AI risk narrative · 2 w · **the core value**

**Build:** answer "why is my project yellow?" grounded in S12's score and S11's data ·
structured output: factors, evidence, forecast, recommended actions · **inspectable
grounding** · explicit refusal when data is insufficient · no scoring inside the model

**Not:** actions that mutate anything · multi-turn chat · agents · write-back to Jira

**Done when**
- [ ] Explanation generated for the real connected project
- [ ] Every factual claim traceable to specific ingested data
- [ ] **With deliberately insufficient data, the system declines rather than inventing**
- [ ] The narrative never contradicts S12's deterministic score
- [ ] Cost and latency per explanation recorded and acceptable

---

## S15 — AI evaluation · 2 w

**Build:** eval dataset from real projects with known outcomes · quality dimensions
(grounded, accurate, useful, non-contradictory) · automated scoring · regression detection
between prompt versions · cost and latency per run · runs in CI

**Not:** a full eval platform · large-scale human labelling · production A/B testing

**Done when**
- [ ] Eval suite runs unattended and produces a score
- [ ] **A deliberately worsened prompt is caught as a regression**
- [ ] Ungrounded claims are detected automatically
- [ ] Cost per insight is known and defensible
- [ ] Eval runs in the pipeline

*Expect friction: .NET's AI eval ecosystem is weaker than Python's. ADR-002 records this
as the most likely reason to add a Python service behind a boundary.*

---

# ⛔ GATE 2 — the falsification test

**Designed to be failed.** Failing here is the most valuable outcome this roadmap can
produce, because everything after it rests on the answer.

- [ ] A real Delivery Manager, shown a real explanation about **their own** project, says
      **"yes — and I didn't know that."**
- [ ] Cost per insight is known and defensible
- [ ] The eval harness produces a quality score you would show someone else
- [ ] Every AI response is grounded in retrievable data, inspectably

| If they say | Meaning | Do |
|---|---|---|
| *"I already knew that"* | Insight is real but not valuable | Deepen S11 data or S12 scoring. Do not proceed. |
| *"That's wrong"* | Grounding or data quality failed | Back to S11 / S14. |
| *"Yes, and I didn't know that"* | Premise holds ✅ | Pick tracks based on what they ask for **next** |

---

# AFTER GATE 2

**Pick at most two.** Choose from what Gate 2 revealed, not from what looked interesting
at the start. Deliberately low detail — scoping these now would be guessing.

| Track | Scope | Est. |
|---|---|---|
| **A — Model economics** | 2nd provider · routing · self-hosted Llama vs managed, measured across quality/GPU cost/utilization/latency (idea.md §11) | ~10–12 w |
| **B — Knowledge / RAG** | Ingestion · embeddings · hybrid + vector search · **tenant-isolated indexes** (Principle IV) | ~12–14 w |
| **C — Agentic** | Tool calling · orchestration · human approval workflows · event-triggered agents | ~14 w |
| **D — Engineering Intelligence** | 2nd connector (GitHub) · capacity · technical debt · reliability — **system-level only, never individual ranking** (Principle XI) | ~14 w |
| **E — The engineering system itself** | Multi-agent workflows · agent verification · methodology measurement (idea.md §57.5) | ~10 w |
