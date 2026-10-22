# idea.md Traceability & Compliance Audit

**Audited**: 2026-08-08 · against `idea.md` v0.6 (§1–§59, 2,475 lines)
**Method**: every actionable commitment in the blueprint — BUILD, ENFORCE, RECORD,
PROHIBIT, PROCESS — was extracted section by section, including items appearing only
inside diagrams and code blocks, then reconciled against what actually governs it
today. Roughly 700 commitments.

**Purpose**: prove nothing in the blueprint is silently dropped, and surface where the
blueprint contradicts itself or the roadmap.

---

## Summary

| Disposition | Meaning | Count (approx.) |
|---|---|---|
| **GOVERNED** | Enforced now by a Constitution principle, an ADR, or spec 001 | ~180 |
| **SCHEDULED** | Assigned to a named roadmap slice (S1–S15) | ~120 |
| **DEFERRED** | Post-MVP by explicit decision — Horizon 3 track or §46a non-goal | ~330 |
| **SUPERSEDED** | Deliberately changed by v0.5/v0.6; the blueprint text is historical | ~40 |
| **⚠ UNRESOLVED** | Genuine conflict or gap needing a decision | **13** |

The 13 unresolved items are the substance of this audit. Everything else traces cleanly.
U6 is partially resolved and U13 was added on 2026-08-09; both are dated in place.

---

## Where each layer is governed

| idea.md area | Governed by |
|---|---|
| §7 no individual ranking, §46a Track D caveat | Constitution **Principle XI** |
| §14 §15 service boundaries + data ownership | **Principle III**, **ADR-003** |
| §18 §19 security and tenant isolation | **Principles IV, V**, **ADR-013** |
| §20 §21 observability, correlation, distributed behaviour | **Principle VI**, **ADR-011** |
| §22 architecture governance, §23 pipeline gates | **Principle VII** |
| §24 §27 §35 §39 §42 §56 human authority, authority hierarchy | **Principles I, II** |
| §8 §9 §9a §10 §11 AI platform and model strategy | **Principles VIII, IX**, **ADR-008**, **ADR-009** |
| §13 §17 technology stack and Azure topology | **Constraints**, **ADR-001**, **ADR-002**, **ADR-007**, **ADR-023**, **ADR-012** |
| §29 §30 §47 §51 vertical slices | **Principle X**, `roadmap.md` |
| §25 §36 §37 §40 §41 skills and workflow | **ADR-016**, installed `superpowers` plugin |
| §26 §31 §32 §33 §34 §50 Spec Kit lifecycle | `.specify/`, spec 001 as the worked example |
| §46 §46a §59 horizons, gates, MVP cut line | `roadmap.md` |

---

## ⚠ Unresolved items

These need a decision. Ordered by how much they cost to get wrong.

### U1 — §55 Steps 2, 4, and 6 require five documents that roadmap S1 does not list

`idea.md` §55 names ten setup steps. Roadmap S1 covers the constitution, ADRs, the
domain model, the repository skeleton, `AGENTS.md`, and the skills. It does **not**
cover:

| §55 | Document | Status |
|---|---|---|
| Step 2 | `docs/product/product-vision.md` — personas, MVP, capabilities, priorities | **missing from S1** |
| Step 4 | `docs/architecture/system-architecture.md` — boundaries, APIs, events, databases, security, observability | **missing from S1** |
| Step 6 | `docs/ai/ai-strategy.md` | **missing from S1** |
| Step 6 | `docs/ai/agent-model.md` | **missing from S1** |
| Step 6 | `docs/ai/skill-model.md` | **missing from S1** |

**Assessment.** Steps 2 and 4 are largely *already written* — but in `idea.md` (§3–§7
for vision and personas, §14–§20 for architecture) and in `roadmap.md` (§46a's MVP and
priorities). Extracting them into separate documents risks creating two sources of
truth, which Principle II exists to prevent.

**Recommendation:** satisfy Steps 2 and 4 with **pointers** into idea.md rather than new
prose, following the precedent §58 set for the constitution. Defer Step 6 entirely —
`ai-strategy.md` and `agent-model.md` written before roadmap S13 would be speculation,
and `skill-model.md` is now ADR-016. **Decision needed.**

### U2 — §17 provisions AI Search, which nothing uses until Horizon 3

§17's target architecture includes **Azure AI Search**, and roadmap S6 provisions "the
full §17 architecture". But AI Search exists to serve RAG and vector retrieval, which
is Horizon 3 Track B — deferred, and possibly never built if Gate 2 redirects.

Provisioning it in S6 means paying for an idle service for months and violates
Principle X's prohibition on building for anticipated needs.

**Recommendation:** exclude AI Search from S6. Provision it in Track B, when a consumer
exists. This is a genuine deviation from §17, so it should be recorded — either as an
amendment to §17 or a note in ADR-007. **Applied to roadmap.md; §17 not yet amended.**

### U3 — Skill count is inconsistent across §37, §40, and §55

Three different lists:

- **§37** — 12 skills
- **§40** — 13 skills (adds `architecture/`)
- **§55 Step 8** — 7 skills, with "add domain skills when the corresponding domain is
  implemented"

**Recommendation:** §55 Step 8 wins — it is the only one of the three with a stated
principle behind it, and §40 explicitly warns against oversized skill sets. Build 7:
`architecture`, `dotnet-enterprise`, `azure-architecture`, `distributed-systems`,
`testing`, `security`, `ai-engineering`. The remaining six (`api-design`,
`event-driven`, `observability`, `terraform`, `delivery-management`,
`engineering-management`) arrive with their domains. **Recommendation stands; §37 and
§40 read as full inventories, not as S1 scope.**

### U4 — §43's `src/` includes services that belong to Horizon 3

§43 specifies four projects: `Delivery.Service`, `Engineering.Service`, `AI.Platform`,
`Integration.Service`. But **Engineering Intelligence is Horizon 3 Track D**, and
`AI.Platform` is not built until S13.

Creating empty project folders now would be structure without content, and ADR-003
deliberately introduces services *as their slices arrive*.

**Recommendation:** S1 creates `src/` and `tests/` only. Service projects are created
by the slice that needs them — Platform/Tenancy at S2, Integration at S9, AI Platform at
S13, Engineering never in the MVP. **Decision needed.**

### U5 — §16's event list does not contain the event roadmap S8 builds

§16 names eleven events: `ProjectCreated`, `ProjectUpdated`, `SprintCompleted`,
`ReleaseCreated`, `ReleaseDelayed`, `DeploymentFailed`, `DeploymentCompleted`,
`RiskCreated`, `RiskEscalated`, `IncidentCreated`, `IncidentResolved`.

Roadmap S8 builds **`TenantCreated`**, which is on neither list — because when §16 was
written, tenancy was not thought of as an event source.

**Assessment:** S8's choice is right. Every §16 event depends on delivery data that does
not exist until S11, so using one would make S8 wait for Horizon 2 — but S8 exists to
prove messaging mechanics, and those need only *an* event. `TenantCreated` is the only
event available in Horizon 1.

**Recommendation:** add `TenantCreated` to §16's list. Low-risk. **Not yet applied.**

### U6 — §22 lists eight test types; only four are scheduled

| Test type | Status |
|---|---|
| Unit, Integration, Architecture | roadmap S3 ✓ |
| Contract | project created in S3, first real contract test at S9 |
| **End-to-End** | **unscheduled** |
| **Performance** | **roadmap S7** ✓ — resolved 2026-08-09, see below |
| **Security** | **unscheduled** (secret + dependency scanning is S7, but not security *tests*) |
| AI Evaluation | roadmap S15 ✓ |

**Recommendation:** E2E belongs in S7 once a deployed environment exists. Security
testing is legitimately post-Gate-1. Worth stating explicitly rather than leaving as an
implied gap. **Decision still needed for E2E and Security.**

**✅ RESOLVED (2026-08-09) — Performance / spec 001 SC-003.** Raised during
`/speckit.plan` for S2: SC-003 (95% of tenant reads under 1s at 50 concurrent users
across 20 tenants) has no verification anywhere, and roadmap S2's *Done when* does not
list it — so it was on course to pass unverified and unmarked.

**Decision: SC-003 verification is deferred to roadmap S7**, recorded in spec 001's
[Deferred Requirements](../specs/001-auth-tenant-management/spec.md#deferred-requirements)
and added to S7's *Done when*.

Rationale: S7 is the earliest slice with both a pipeline to run a load test *and* a
deployed environment to run it against. Measuring in S2 was rejected because the number
would be meaningless — S2's database is SQL Server under x86 emulation on an ARM
development machine, which tells you nothing about Azure SQL. S7 is also still before
**Gate 1**, so spec 001 remains fully verified before Horizon 2 begins.

### U7 — §23's pipeline includes a QA environment; roadmap S7 has only dev

§23 specifies `Dev → QA → Approval → Production`. Roadmap S7 builds dev only, and
ADR-007 defers QA and production explicitly.

**Assessment:** correct for Horizon 1 — a QA environment with no users and no release
process is cost without function. But §23 is unamended, so the blueprint and roadmap
disagree in writing.

**Recommendation:** note in §23 that QA and production arrive post-Gate-1. **Not yet
applied.**

### U8 — §6's 14 delivery entities vs §46a's "projections, not native entities"

§6 lists Portfolio, Program, Project, Initiative, Epic, Feature, Sprint, Milestone,
Release, Dependency, Risk, Issue, Team, Capacity as concepts to model. §46a and §57.2
say the MVP uses ingested projections and that an entity is native only if the platform
adds something the source system lacks.

**Assessment:** resolved in principle — §6 is a domain vocabulary, not a build list, and
§46a governs. But §6 reads as a commitment, and the domain model in S1 will have to make
the distinction concrete: which of the 14 are projections, which are native (Risk almost
certainly), and which are neither in the MVP.

**Recommendation:** S1's `domain-model.md` classifies all 14 explicitly. **Assign to S1.**

### U9 — §4's five personas read as commitments; §46a serves only one

§4 lists ~23 needs across Delivery Manager, Engineering Manager, Architect, SRE, and
Executive. §46a cuts the MVP to the Delivery Manager alone.

**Assessment:** governed by §46a, and the reasoning is recorded. Flagged only because §4
is unmarked — a reader arriving at §4 first would reasonably infer all five are in scope.

**Recommendation:** add a pointer at §4 to §46a. Cosmetic but prevents real confusion.
**Not yet applied.**

### U10 — §19's tenant sub-entities are mostly deferred

§19 models Users, Teams, Projects, Policies, Documents, Integrations, and AI
Configuration under Tenant. Spec 001 (S2) implements only Users, Memberships, and
Invitations.

**Assessment:** correctly sequenced — Integrations arrive at S9, AI Configuration at S13,
Documents in Track B, Teams and Projects as projections at S11, Policies never in the
MVP. **No action; recorded for completeness.**

### U11 — §57.5's Product B success measure is still undefined

`idea.md` §57.5 records this as an open issue and proposes a candidate: *the proportion
of merged changes that passed spec → plan → tasks → implementation without a human
rewriting the agent's output.* It also says not to set a target until real data exists.

**Assessment:** genuinely open, and correctly so. Setting a target now would be
invented.

**Recommendation:** start *collecting* the measure from S2 — it costs nothing to note,
per slice, whether the agent's output needed rewriting. Without the habit, there will be
no data at Gate 2 either. **Decision needed.**

### U12 — Enforcement gaps acknowledged in the ADRs

Four decisions are currently enforced by human review where Principle VII would prefer a
gate. Each is recorded in its ADR's Compliance section:

| Gap | ADR | Proposed fix | Status |
|---|---|---|---|
| Nothing prevents a raw SQL query or background job bypassing the tenant filter | ADR-013 | Architecture test in S3 restricting raw SQL outside audited helpers | **Addressed.** Raw SQL: `RawSqlGates.cs` (FR-010/FR-011). Background jobs: `BackgroundJobGates.cs` (FR-012). |
| Nothing prevents calling a non-Azure managed service from app code | ADR-001 | Architecture test on outbound SDK dependencies | **Addressed** by `DependencyPinGates.cs` (FR-014/FR-017/FR-018). |
| Nothing prevents portal changes to infrastructure | ADR-012 | Restrict human subscription write access; changes only via pipeline identity (S7) | Open — S7's job. |
| Nothing asserts `.claude/skills` remains a symlink | ADR-016 | Cheap CI check (S7) | Open — S7's job. |

**FR-012 vs FR-027 — two different halves of the background-job gap.** `BackgroundJobGates.cs`'s
FR-012 closes the *direct route*: a structural gate rejecting any background job whose
constructor takes `TenancyDbContext` (or a persistence port) directly, so a job can no longer be
written to sidestep tenant context by construction. FR-027 (already done, commit `3aebea6`)
closes the *underlying property* instead: a runtime backstop ensuring any insert made with no
tenant context set simply fails, regardless of which code path — job, handler, or otherwise —
produced it. Together they close both the structural opening and the property it would have
exploited.

**Corrected framing.** The original note above overstated the gap as "background jobs" in
general. In fact reads, updates, and deletes were already safe by construction: the tenant-scoping
query filter fails closed, so a query issued against the wrong tenant returns nothing rather than
leaking data (see `MembershipRepository.cs`, `InvitationRepository.cs`, `UserRepository.cs`).
**Insert was the one operation without an equivalent backstop** — nothing stopped an insert from
being persisted with the wrong (or no) tenant context, which is exactly what FR-027's guard now
closes. FR-012 additionally removes the specific job-shaped route to reaching that gap. **Resolved
in S3.**

### U13 — §17 and §20 name Azure Monitor / App Insights; the telemetry backend is now New Relic

`idea.md` §17 lists Azure Monitor, Application Insights, and Log Analytics as provisioned
infrastructure, and §20's trace diagram is framed around them.
[ADR-018](adr/ADR-018-new-relic-telemetry-backend.md) (2026-08-09) makes **New Relic** the
default telemetry backend over OTLP, with Application Insights as an optional secondary
exporter.

**Assessment: applied, blueprint unamended** — the same disposition as U2. The change was
directed by the project owner, who owns product direction, and it is recorded in ADR-018 with
the exception ADR-001 requires for a non-Azure service. But `idea.md` is *higher authority than
an ADR* under Principle II, so an agent does not edit it: it proposes.

Worth noting that **nothing downstream broke.** ADR-011's instrumentation decision, spec 001,
its plan, research, and data model all required no change — the vendor-neutrality ADR-011 paid
configuration cost for turned out to be real. That is a finding, not a formality.

**Recommendation:** amend §17 to name the telemetry backend as a *decision recorded in an ADR*
rather than a fixed Azure service, and add a sentence to §20 clarifying that the trace
requirement is backend-independent — which is what OpenTelemetry is for. Low risk, and it stops
the blueprint from quietly contradicting the running system. **Not yet applied.**

Two consequences to carry forward rather than rediscover:

- **Cardinality:** New Relic's limits apply to metrics, not spans. `tenant.id` belongs on spans
  and logs, **never as a metric dimension** — otherwise Principle VI's tenant-annotation
  requirement collides with a hard per-day limit as tenant count grows.
- **S4 gains, not loses.** App Insights needed an Azure subscription, so ADR-011 had accepted a
  local collector for S4's proof. New Relic's free tier means S4 can run against a real backend
  two slices earlier than planned.

---

## Superseded blueprint text

Recorded so the deviations are deliberate rather than accidental. Each is explained in
idea.md §57 or §59.

| Blueprint text | Superseded by | Why |
|---|---|---|
| §46 eight sequential phases | §46 three horizons + gates | A phase has no exit condition (§59.1) |
| §9's eleven gateway responsibilities built up front | §9a, ADR-008 | Speculative generality (§57.3) |
| Phase 2 native entities before integration | Horizon 2 ordering | Data availability unvalidated (§57.2) |
| Phase 5 AI in the scoring path | S12 before S13–S14 | Principle VIII (§57.4) |
| §43 `docs/constitution.md` as the file | §58 — `.specify/memory/`, pointer permitted | Tooling reads it there; no duplication |
| §45 ADR-006 as a separate record | ADR-003 | Boundary and data ownership are one decision |
| §45 ADR-015 as an ADR | The Constitution itself | Higher authority; two sources would drift |
| §30 "Service Template" as a slice | Dropped | A folder layout, not a slice |

---

## Open decisions

**Seven** items need a human decision (was six; **U13** added 2026-08-09). Five are
recommendations awaiting confirmation (**U1, U4, U6, U11**, and the amendments in
**U5, U7, U9**); two are applied but leave the blueprint unamended (**U2**, **U13**).

**U6 is partially resolved** (2026-08-09): the Performance gap — spec 001 SC-003 — is
assigned to roadmap S7. E2E and Security test scheduling remain open.

**U13** (2026-08-09) records that `idea.md` §17/§20 still name Azure Monitor and
Application Insights while [ADR-018](adr/ADR-018-new-relic-telemetry-backend.md) has made
New Relic the telemetry backend. Applied in practice; the blueprint amendment is
recommended but not made, because `idea.md` outranks an ADR.

Two are assigned and need no decision: **U8** → S1's domain model, **U12** → S3
architecture tests.

Per Constitution Principle II, none of these were resolved unilaterally — a blueprint
amendment is a change to architectural authority, and an agent proposes rather than
decides.
