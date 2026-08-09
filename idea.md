# AI Engineering & Delivery Intelligence Platform

## Master Architecture, Product Strategy & AI-Assisted Development Blueprint

**Version:** 0.6
**Status:** Foundational / First Slice Specified / Constitution Ratified
**Changes in 0.6:** Eight phases replaced by three horizons separated by gates (§46); orientation declared research-first with a mandatory safeguard (§59); MVP cut line restated as Horizons 1–2 (§46a); committed plan reduced from ~52 slices to 15 (§46). See §59 for the reasoning.
**Changes in 0.5:** Roadmap resequenced to integration-first (§57.2); MVP cut line and product non-goals added (§46a); AI Gateway scope reduced and deferred (§9a); review of v0.4's weaknesses recorded (§57).
**Primary Technology:** .NET / Azure / Containers / AI
**Development Model:** Specification-Driven + AI-Assisted Engineering + Vertical Slices

---

# 1. Purpose

This document is the primary blueprint for building the AI Engineering & Delivery Intelligence Platform.

It defines:

1. Product vision and business capabilities
2. Enterprise architecture
3. AI architecture and strategy
4. Engineering principles
5. AI-assisted development methodology
6. Spec Kit usage
7. Agent workflow
8. Custom skill architecture
9. Development roadmap
10. Initial implementation strategy

The project has two simultaneous objectives:

### Product Objective

Build a real enterprise-grade SaaS platform that provides AI-powered delivery and engineering intelligence.

### Engineering / Research Objective

Explore how AI agents, specifications, reusable skills, automated testing, and enterprise architecture can be combined into a modern software engineering system.

---

# 2. North Star

> **Build an enterprise-grade AI Engineering & Delivery Intelligence Platform while researching how AI agents can participate safely, effectively, and economically in modern software engineering.**

The long-term vision is an:

> **AI-powered Engineering Operating System**

for software organizations.

---

# 3. Product Vision

The platform becomes an intelligence layer across existing enterprise engineering systems.

It does not attempt to replace:

* Jira
* Azure DevOps
* GitHub
* ServiceNow
* PagerDuty
* CI/CD platforms
* Observability platforms

Instead:

```text
Enterprise Systems
       ↓
Integration
       ↓
Unified Engineering Data
       ↓
Analytics
       ↓
AI / Intelligence
       ↓
Recommendations
       ↓
Human-approved Actions
```

---

# 4. Personas

## Delivery Manager

Primary question:

> Are we going to deliver?

Needs:

* Project health
* Program health
* Release readiness
* Risks
* Dependencies
* Capacity
* Forecast
* Escalations
* Executive reporting

---

## Engineering Manager

Primary question:

> Is engineering healthy and capable of delivering sustainably?

Needs:

* Engineering capacity
* Productivity
* Quality
* Reliability
* Technical debt
* Developer experience
* On-call burden
* Knowledge concentration
* Architecture health

---

## Architect

Primary question:

> Is our architecture healthy, secure, scalable, and sustainable?

---

## SRE / DevOps

Primary question:

> Are our systems reliable and operable?

---

## Executive

Primary question:

> Are we delivering business value while managing technology risk?

---

# 5. Product Domains

```text
AI Engineering & Delivery Intelligence Platform
│
├── Delivery Intelligence
│
├── Engineering Intelligence
│
├── AI Platform
│
├── Integration Platform
│
├── Analytics / Reporting
│
└── Platform / Security / Governance
```

---

# 6. Delivery Intelligence

Core concepts:

```text
Portfolio
Program
Project
Initiative
Epic
Feature
Sprint
Milestone
Release
Dependency
Risk
Issue
Team
Capacity
```

The platform should eventually answer:

> Why is my project yellow?

rather than simply displaying:

> Project = Yellow

It should provide:

* evidence
* contributing factors
* forecast
* recommended actions

---

# 7. Engineering Intelligence

Major capabilities:

```text
Engineering Intelligence
│
├── Productivity
├── Capacity
├── Engineering Allocation
├── Technical Debt
├── Reliability
├── Architecture Health
├── Knowledge Concentration
└── Developer Experience
```

The platform should measure **engineering systems**, not rank individual employees.

---

# 8. AI Platform

AI is a shared platform capability.

```text
AI Platform
│
├── AI Gateway
├── Model Router
├── Agent Runtime
├── Prompt Management
├── RAG / Knowledge
├── AI Evaluation
├── AI Governance
└── AI Cost Management
```

Business services should consume AI through the AI Platform rather than directly coupling themselves to a specific model provider.

---

# 9. AI Gateway

Application:

```text
Business Service
      ↓
AI Gateway
      ↓
Model Router
      ↓
Model Provider
```

The AI Gateway manages:

* provider abstraction
* model selection
* prompt execution
* context
* tools
* policies
* cost
* observability
* rate limits
* security
* evaluation

---

# 9a. AI Gateway — Scope Discipline

§9 lists eleven responsibilities for the AI Gateway. Building all of them before a single consumer exists would be exactly the speculative generality §14 warns against.

The gateway is therefore built in two stages:

**Stage 1 — when the first AI consumer appears.** Only what that consumer actually needs:

```text
provider abstraction
prompt execution
token + cost tracking
telemetry
```

**Stage 2 — when a second, materially different consumer appears.** Only then does routing become a real problem rather than an imagined one:

```text
model routing
policies
rate limits
evaluation harness
tool orchestration
```

Rule: **no gateway capability is built until a named consumer requires it.** The abstraction seam must exist from the start so callers never touch a provider directly (Constitution principle 9); the machinery behind that seam grows on demand.

---

# 10. Model Strategy

The system must remain model-provider agnostic.

Potential providers include:

* Azure-hosted models
* OpenAI-compatible models
* Llama
* future enterprise models

Applications should request capabilities rather than hard-code models.

Example:

```text
Capability:
ReleaseRiskAnalysis
```

The model router determines the appropriate model.

---

# 11. Llama Strategy

Llama is an important option for:

* experimentation
* private inference
* cost optimization
* model specialization
* infrastructure control

However:

> Self-hosted Llama is not automatically cheaper.

The platform must compare:

```text
Quality
+
GPU Cost
+
Utilization
+
Latency
+
Operational Cost
+
Security
+
Availability
```

against managed models.

Model choice should therefore be **measured**, not ideological.

---

# 12. AI Agents

Potential agents:

```text
Delivery Agent
Risk Agent
Dependency Agent
Release Agent
Incident Agent
RCA Agent
Engineering Agent
Capacity Agent
Executive Agent
```

Agents follow:

```text
Observe
   ↓
Analyze
   ↓
Reason
   ↓
Recommend
   ↓
Act
```

High-risk actions require human approval.

---

# 13. Enterprise Architecture

The platform will be:

* cloud-native
* containerized
* service-oriented
* event-driven where appropriate
* observable
* secure
* multi-tenant
* infrastructure-as-code driven

Primary stack:

```text
.NET
ASP.NET Core
C#
Azure
Docker
AKS
Terraform
Azure Service Bus
Microsoft Entra ID
OpenTelemetry
```

---

# 14. Service-Oriented Architecture

Services are organized around **business capabilities**.

Example:

```text
API Gateway
    │
    ├── Delivery Service
    │
    ├── Engineering Service
    │
    ├── Integration Service
    │
    └── AI Platform
```

Service boundaries are based on:

* bounded contexts
* business ownership
* data ownership
* security boundaries
* scaling characteristics
* lifecycle

We will **not create microservices merely because we can**.

---

# 15. Data Ownership

Each service owns its data.

```text
Delivery Service
      ↓
Delivery Database

Engineering Service
      ↓
Engineering Database

AI Platform
      ↓
AI Database
```

Cross-service database access is prohibited.

Communication occurs through:

* APIs
* events
* messaging

---

# 16. Event-Driven Architecture

Azure Service Bus is the default asynchronous messaging mechanism.

Potential events:

```text
ProjectCreated
ProjectUpdated
SprintCompleted
ReleaseCreated
ReleaseDelayed
DeploymentFailed
DeploymentCompleted
RiskCreated
RiskEscalated
IncidentCreated
IncidentResolved
```

Example:

```text
ReleaseDelayed
      ↓
Azure Service Bus
      ↓
+----------+----------+----------+
|          |          |          |
AI       Analytics  Notification
```

---

# 17. Azure Architecture

Target architecture:

```text
Azure Front Door
       ↓
Azure API Management
       ↓
AKS
       ↓
+------+-------+----------------+
|              |                |
Services       Workers          AI
|              |                |
+--------------+----------------+
       ↓
+------+-------+---------+------+
|              |         |      |
Azure SQL   Service   Storage  AI Search
            Bus
```

Supporting services:

* Azure Container Registry
* Azure Key Vault
* Microsoft Entra ID
* Azure Monitor
* Application Insights
* Log Analytics
* Managed Identity
* Private Endpoints

---

# 18. Security

Principles:

* Microsoft Entra ID
* Managed Identity
* RBAC
* Least Privilege
* Key Vault
* Private Networking
* Tenant Isolation
* Encryption
* Audit Logging
* API Security

---

# 19. Multi-Tenancy

The SaaS architecture must support tenant isolation across:

* APIs
* data
* documents
* vector indexes
* AI context
* events
* logs
* authorization

Conceptually:

```text
Tenant
│
├── Users
├── Teams
├── Projects
├── Policies
├── Documents
├── Integrations
└── AI Configuration
```

---

# 20. Observability

OpenTelemetry should provide common instrumentation.

Observe:

* logs
* metrics
* traces
* health checks
* dependencies
* AI telemetry
* token usage
* model latency
* AI cost

Distributed traces should allow:

```text
Frontend
   ↓
API
   ↓
Delivery Service
   ↓
Service Bus
   ↓
AI Agent
   ↓
AI Search
   ↓
LLM
```

to be understood as one logical transaction.

---

# 21. Engineering Principles

The platform follows:

* Domain-Driven Design
* SOLID
* Clean Architecture
* Dependency Inversion
* REST
* Event-driven architecture
* asynchronous messaging
* OpenTelemetry
* automated testing
* CI/CD
* Infrastructure as Code

Distributed-system behavior must explicitly handle:

* timeout
* retry
* idempotency
* circuit breaker
* dead-letter queues
* duplicate messages
* eventual consistency
* correlation IDs

---

# 22. Testing Strategy

```text
Unit Tests
     ↓
Integration Tests
     ↓
Contract Tests
     ↓
Architecture Tests
     ↓
End-to-End Tests
     ↓
Performance Tests
     ↓
Security Tests
     ↓
AI Evaluation
```

Architecture tests should automatically enforce important boundaries.

Example:

```text
Domain cannot depend on Infrastructure.

Delivery Service cannot access AI database.

Services cannot bypass integration boundaries.

AI requests must go through AI Gateway.
```

---

# 23. CI/CD

```text
Commit
  ↓
Build
  ↓
Unit Tests
  ↓
Architecture Tests
  ↓
Integration Tests
  ↓
Security Scan
  ↓
Container Build
  ↓
Container Scan
  ↓
ACR
  ↓
Dev
  ↓
QA
  ↓
Approval
  ↓
Production
```

AI evaluation will eventually become part of the pipeline.

---

# 24. AI-Assisted Development Philosophy

This project will use AI heavily, but AI does not own the product.

The responsibility model is:

### Human

Owns:

* vision
* business priorities
* scope
* architecture ownership
* risk acceptance
* production authorization

### AI

Assists with:

* research
* analysis
* implementation
* testing
* documentation
* architecture analysis
* code review
* debugging
* refactoring

Principle:

> **AI assists execution; humans retain ownership of intent, architecture, risk, and authorization.**

---

# 25. The Development System

The development methodology has five major layers.

```text
1. Specification
2. Rules
3. Development Workflow
4. Knowledge
5. Execution
```

They map to:

```text
Specification → Spec Kit

Rules → Constitution + ADRs

Development Workflow → Superpowers-style practices

Knowledge → Custom Skills

Execution → AI Coding Agent
```

---

# 26. Spec Kit — WHAT We Build

Spec Kit answers:

> **What are we building?**

It transforms product intent into:

```text
Intent
  ↓
Specification
  ↓
Clarification
  ↓
Technical Plan
  ↓
Tasks
```

Spec Kit is therefore not merely a task generator.

It is a **specification-to-implementation planning system**.

---

# 27. Important Distinction: Roadmap vs Spec Kit

Spec Kit does not replace Product Management.

The human still determines:

```text
WHY
WHAT
PRIORITY
SCOPE
SEQUENCE
```

Spec Kit helps transform that decision into:

```text
REQUIREMENTS
DESIGN
PLAN
TASKS
```

Therefore:

```text
Human Product Decision
          ↓
      Roadmap
          ↓
       Feature
          ↓
      Spec Kit
          ↓
 Specification
          ↓
 Technical Plan
          ↓
 Tasks
```

---

# 28. Roadmap Structure

The product roadmap should be divided into major phases.

Example:

```text
MVP
│
├── HORIZON 1 — Enterprise Foundation        8 slices  ~12–14 wks
│        │
│      GATE 1 — deployed, observable, governed
│        │
└── HORIZON 2 — Real Data and First AI       7 slices  ~14 wks
         │
       GATE 2 — a Delivery Manager learns something new
         │
POST-MVP │
         ▼
   HORIZON 3 — Research Tracks (pick at most 2)
         │
         ├── Track A — Model Economics
         ├── Track B — Knowledge / RAG
         ├── Track C — Agentic Platform
         ├── Track D — Engineering Intelligence
         └── Track E — Product B / Engineering System
```

A horizon is finishable. A gate is a question whose answer determines whether the
next horizon is still worth building. **A phase is neither** — which is why v0.6
stopped using them.

The authoritative roadmap is §46. This is a summary.

However, each phase should **not** become one giant implementation task.

Each phase is broken into capabilities.

---

# 29. Vertical Slice Principle

This is a core development principle.

Avoid:

```text
Phase 1
  ↓
500 tasks
  ↓
3 months coding
  ↓
First deployment
```

Instead use:

```text
Small Capability
      ↓
Specification
      ↓
Implementation
      ↓
Test
      ↓
Deploy
      ↓
Feedback
      ↓
Next Capability
```

Each slice should produce **working software**.

---

# 30. Example: Platform Foundation

*This section is the origin of Horizon 1's slice list (§46). Its eight slices map
to S2–S8 there, with S1 (constitution + ADRs) prepended and "Service Template"
dropped as a folder layout rather than a slice. §59.3 explains why spec 001
currently violates this decomposition.*

Instead of one huge horizon:

```text
Platform Foundation
```

break it into vertical slices:

```text
Slice 1
Authentication + basic API

Slice 2
Tenant creation + authorization

Slice 3
Database persistence

Slice 4
Service Bus integration

Slice 5
Observability

Slice 6
Containerization

Slice 7
Terraform deployment

Slice 8
CI/CD
```

Each slice should be independently testable and deployable where practical.

---

# 31. Feature-Level Spec Kit Workflow

For every meaningful capability:

```text
Product Intent
      ↓
/specify
      ↓
Feature Specification
      ↓
/clarify
      ↓
Resolved Requirements
      ↓
/plan
      ↓
Technical Implementation Plan
      ↓
/tasks
      ↓
Implementation Tasks
      ↓
AI Agent
      ↓
Implementation
      ↓
Tests
      ↓
Review
      ↓
Verification
```

The exact Spec Kit commands may evolve with future versions, but this logical lifecycle is the project's standard.

---

# 32. Example: Tenant Management

Product requirement:

> Users need to create and manage tenants.

Spec Kit produces a specification containing:

### User Story

```text
As an administrator,
I want to create a tenant,
so that users and projects can be isolated.
```

### Requirements

```text
1. Create tenant
2. Update tenant
3. Assign tenant administrator
4. Isolate tenant data
5. Enforce authorization
```

### Acceptance Criteria

```text
Given an authenticated administrator
When a tenant is created
Then the tenant receives a unique identifier
and is isolated from other tenants.
```

---

# 33. Technical Plan

The plan may identify:

```text
1. Tenant domain model
2. Tenant database schema
3. Repository
4. Tenant API
5. Authorization
6. Middleware
7. Integration tests
8. Architecture tests
9. Observability
10. Container configuration
```

---

# 34. Tasks

Tasks become implementation units.

Example:

```text
T001 Create Tenant domain model

T002 Create Tenant repository

T003 Create database migration

T004 Create Tenant API

T005 Add tenant authorization

T006 Add integration tests

T007 Add architecture tests

T008 Add telemetry
```

The AI coding agent can then execute a selected subset:

```text
Implement T001–T004.
```

followed by:

```text
Implement T005–T008.
```

---

# 35. Do Not Treat Tasks as a Blind To-Do List

Tasks are implementation guidance.

The agent must still:

* inspect the repository
* understand existing architecture
* check relevant ADRs
* load relevant skills
* run tests
* verify assumptions

If implementation reveals that the specification or architecture is wrong:

> **Stop and propose a change.**

Do not silently redesign the system.

---

# 36. Superpowers — HOW We Work

Superpowers-style practices provide development discipline.

They are concerned primarily with:

```text
How should the work be executed?
```

Typical practices include:

* brainstorming
* planning
* TDD
* debugging
* code review
* verification
* structured implementation

Superpowers should not become the product's architectural authority.

---

# 37. Custom Skills — WHAT the Agent Needs to Know

Custom skills contain project-specific knowledge.

Examples:

```text
.NET Enterprise
Azure Architecture
Distributed Systems
API Design
Event-Driven Architecture
Security
Terraform
Testing
Observability
AI Engineering
Delivery Management
Engineering Management
```

A skill is:

> **Reusable knowledge + instructions + constraints + patterns**

It is not an agent.

---

# 38. AI Coding Agent — WHO Executes

Potential agents include:

* Claude Code
* Codex
* GitHub Copilot
* other compatible coding agents

The platform should avoid coupling its engineering process to one specific agent.

The agent is replaceable.

The durable assets are:

```text
Specifications
Constitution
ADRs
Architecture
Skills
Tests
Source Code
```

---

# 39. Complete Mental Model

```text
                       HUMAN
                         │
                    Product Intent
                         │
                         ▼
                  +--------------+
                  |   SPEC KIT   |
                  +--------------+
                         │
                         │ WHAT
                         ▼
               Feature Specification
                         │
                         ▼
             Constitution + ADRs
                         │
                  Rules / Authority
                         │
                         ▼
            Development Workflow
          (Superpowers-style practices)
                         │
                         │ HOW
                         ▼
                 AI Coding Agent
                    /        \
                   /          \
                  ▼            ▼
       Workflow Skills     Custom Skills
       How to work         What to know
                  \            /
                   \          /
                    ▼        ▼
                       CODE
                         │
                    TEST / REVIEW
                         │
                    VERIFICATION
                         │
                    HUMAN APPROVAL
                         │
                      DEPLOY
```

---

# 40. Custom Skill Repository

Proposed structure:

```text
.agent/
└── skills/
    ├── architecture/
    ├── dotnet-enterprise/
    ├── azure-architecture/
    ├── distributed-systems/
    ├── api-design/
    ├── event-driven/
    ├── security/
    ├── terraform/
    ├── testing/
    ├── observability/
    ├── ai-engineering/
    ├── delivery-management/
    └── engineering-management/
```

Each skill should have a narrow responsibility.

Avoid one giant:

```text
enterprise-everything
```

Prefer:

```text
azure-architecture
```

over:

```text
azure-dotnet-kubernetes-security-ai-everything
```

---

# 41. Skill Loading Principle

The agent should load only skills relevant to the task.

For example:

### Delivery Risk Feature

Potential skills:

```text
delivery-management
dotnet-enterprise
api-design
ai-engineering
azure-architecture
testing
```

### Terraform AKS Feature

Potential skills:

```text
azure-architecture
terraform
security
observability
```

This reduces unnecessary context and conflicting instructions.

---

# 42. Source-of-Truth Hierarchy

This hierarchy must be respected:

```text
Business / Product Direction
            ↓
Product Specification
            ↓
Engineering Constitution
            ↓
Architecture
            ↓
ADR
            ↓
Feature Specification
            ↓
Implementation Plan
            ↓
Code / Tests
            ↓
Agent Skills
```

Skills do not override product requirements or architectural authority.

If a skill conflicts with an ADR:

> The ADR wins.

If the agent discovers that an ADR appears wrong:

> The agent proposes an ADR change.

It should not silently override it.

---

# 43. Repository Structure

```text
/
├── src/
│   ├── Delivery.Service/
│   ├── Engineering.Service/
│   ├── AI.Platform/
│   └── Integration.Service/
│
├── tests/
│   ├── UnitTests/
│   ├── IntegrationTests/
│   ├── ContractTests/
│   ├── ArchitectureTests/
│   └── EndToEndTests/
│
├── infrastructure/
│   └── terraform/
│
├── deployment/
│   ├── helm/
│   └── kubernetes/
│
├── docs/
│   ├── product/
│   ├── architecture/
│   ├── adr/
│   ├── domain/
│   ├── ai/
│   └── constitution.md
│
├── specs/
│
├── .agent/
│   └── skills/
│
├── AGENTS.md
└── CLAUDE.md
```

---

# 44. Engineering Constitution

Initial principles:

```text
1. Azure-first
2. .NET-first
3. Business-capability-oriented services
4. Explicit data ownership
5. API/event-based service communication
6. Observable-by-default
7. Terraform-managed infrastructure
8. Secure-by-default
9. AI-provider abstraction
10. Human approval for high-risk AI actions
11. Automated testing
12. Architecture governance
13. AI evaluation
14. Cost-aware AI usage
15. System-level engineering metrics
```

The constitution is the engineering "law" of the repository.

---

# 45. ADRs

Architecture decisions should be documented.

Examples:

```text
ADR-001 Why Azure?
ADR-002 Why .NET?
ADR-003 Service-oriented architecture
ADR-004 Service boundaries
ADR-005 Azure Service Bus
ADR-006 Data ownership
ADR-007 AKS
ADR-008 AI Gateway
ADR-009 Model abstraction
ADR-010 RAG
ADR-011 OpenTelemetry
ADR-012 Terraform
ADR-013 Multi-tenancy
ADR-014 AI governance
ADR-015 AI-assisted development methodology
```

---

# 46. Roadmap — Three Horizons *(restructured in v0.6)*

> **Execution detail lives in [roadmap.md](roadmap.md).** This section states the
> structure and reasoning; roadmap.md is the working document with per-slice scope,
> non-scope, outcomes, and proof checklists. Keep the two in sync — if a slice
> changes, change roadmap.md first and reflect the structural consequence here.

v0.4 and v0.5 expressed the roadmap as eight sequential phases. That structure
had a defect independent of its content: **every phase was equally mandatory, so
nothing could be cut and no horizon could be finished.** The estimated ~52 slices
amounted to 12–24 months with no decision point anywhere in it.

This version replaces phases with **horizons separated by gates.** A horizon is
finishable. A gate is a question whose answer determines whether the next horizon
is still the right thing to build.

## Orientation: research-first

When breadth of technology and speed to user value conflict, **breadth wins**
(§59). The platform is a research laboratory (§52) as much as a product, so the
roadmap deliberately exercises the full enterprise stack rather than taking the
shortest path to a demo.

This is an accepted trade, not an oversight. Horizon 1 is roughly three times
longer than a product-first equivalent would be. What it buys is real experience
of AKS, Terraform, managed identity, private networking, distributed messaging,
and architecture governance under genuine conditions.

**The safeguard, and it is not optional:** every technology adopted MUST be
exercised by a real capability under real conditions. A technology stood up and
never driven hard teaches only its happy path, which is the least useful thing to
know about it. Service Bus without duplicate delivery and a dead-letter replay is
not learning Service Bus. AKS without a failed rollout is not learning AKS. See
§59.2.

Working assumption: full-time effort, 1–2 weeks per slice.

---

## Horizon 1 — Enterprise Foundation

**8 slices · ~12–14 weeks**

*Objective: a real person authenticates against something you deployed to Azure
through a pipeline, and you can explain its behaviour from telemetry alone.*

```text
S1  Constitution + ADRs                        (in progress)
S2  Auth + tenant + persistence                (local, tested)
S3  Architecture tests + test pyramid
S4  Observability — OTel, correlated traces
S5  Containerization
S6  Terraform → AKS, APIM, Key Vault, managed identity, private endpoints
S7  CI/CD with all gates
S8  Service Bus — one real event, idempotency, retry, DLQ
```

**Research targets:** .NET clean architecture, DDD, Entra ID, multi-tenant
isolation, OpenTelemetry, Terraform, AKS, private networking, architecture
governance, distributed-systems failure handling.

### Gate 1 — must pass before Horizon 2

- [ ] A change reaches Azure through the pipeline in under 20 minutes with no
      manual step.
- [ ] A deliberately induced failure is diagnosed from telemetry alone, without
      local reproduction, in under 10 minutes.
- [ ] Cross-tenant access is refused for every tenant-scoped operation, proven by
      automated tests.
- [ ] A duplicated Service Bus message is demonstrably handled idempotently, and
      a dead-lettered message can be replayed.
- [ ] An architectural boundary violation fails the build.
- [ ] The whole environment provisions into an empty subscription from code alone.

If Gate 1 fails, **do not start Horizon 2.** Everything after this point assumes
the foundation holds; building on an unproven one converts one problem into many.

---

## Horizon 2 — Real Data and First AI

**7 slices · ~14 weeks**

*Objective: a real Delivery Manager connects their real Jira or Azure DevOps
project and learns something they did not already know.*

```text
S9   Integration service + one connector, read-only (Jira OR ADO — pick one)
S10  Sync scheduling, incremental sync, rate limits, auth expiry, partial failure
S11  Ingested delivery data model + data freshness visibility
S12  Deterministic project health score          (no AI — Principle VIII)
S13  AI seam + one provider + prompt management + token/cost/telemetry
S14  First AI capability — risk narrative, structured output, grounded
S15  AI evaluation harness
```

**Research targets:** integration patterns against hostile real-world APIs, sync
and idempotency at scale, deterministic scoring, provider abstraction, structured
LLM output, grounding, token economics, AI evaluation methodology.

Note the ordering of S12 before S13–S14. The health score is arithmetic and must
be reproducible; AI explains it. This is Principle VIII applied, and it is the
single most important sequencing decision in the roadmap.

### Gate 2 — the only gate that matters commercially

- [ ] A real Delivery Manager, shown a real risk explanation about their own
      project, says **"yes, and I didn't know that."**
- [ ] Cost per insight is known and defensible.
- [ ] The evaluation harness produces a quality score you would show someone else.
- [ ] Every AI response is grounded in retrievable data, and the grounding is
      inspectable.

Gate 2 is a falsification test, not a milestone. If the Delivery Manager says
*"I already knew that"* or *"that's wrong,"* the product premise is wrong and
Horizon 3 would have been built on a false assumption. Failing here early is the
most valuable outcome the roadmap can produce.

---

## Horizon 3 — Research Tracks (parallel, not sequential)

**~5–7 slices per track · ~10–14 weeks per track**

Horizon 3 is deliberately **not** a sequence, because after Gate 2 there is no
longer a single obvious next thing. It is a menu of independent tracks, each a
coherent research programme. Ordering them now would be guessing.

```text
Track A — Model Economics
  Second provider · model routing · capability-based selection
  Self-hosted Llama vs managed comparison (§11)
  Quality/cost/latency/utilization measurement

Track B — Knowledge & RAG
  Knowledge ingestion · document processing · embeddings
  Hybrid + vector search · grounded responses
  Tenant-isolated vector indexes (Principle IV)

Track C — Agentic Platform
  Tool calling · agent orchestration · human approval workflows
  Event-triggered agents · controlled automation

Track D — Second Domain: Engineering Intelligence
  Second connector (GitHub) · engineering metrics · capacity
  Technical debt · reliability · architecture health
  System-level only, never individual ranking (Principle XI)

Track E — Product B: The Engineering System Itself
  Multi-agent workflows · agent verification
  Automated architecture governance · methodology measurement (§57.5)
```

**Selection rule: pick at most two tracks.** Running all five is how this project
returns to being a 24-month plan with no decision points. Choose based on what
Gate 2 actually revealed, not on what looked interesting at the outset.

---

## Summary

| Horizon | Slices | Duration | Finishable outcome |
|---------|--------|----------|--------------------|
| 1 — Enterprise Foundation | 8 | ~12–14 wks | Deployed, observable, governed platform |
| 2 — Real Data & First AI | 7 | ~14 wks | A Delivery Manager learns something new |
| 3 — Research Tracks | 5–7 per track | ~10–14 wks each | Depends on Gate 2 |

**Horizons 1 + 2 = 15 slices, roughly 7 months full-time.** That is the whole
committed plan. Everything beyond it is explicitly undecided, and that is the
point — v0.5's ~52 slices were not a plan, they were an inventory of ambitions.

---

# 46a. MVP Cut Line & Product Non-Goals *(new in v0.5)*

v0.4 described eight phases with no statement of what constitutes a releasable product. Without a cut line, every phase is equally mandatory and nothing is ever finishable.

## The MVP is Horizons 1 and 2 *(updated in v0.6)*

```text
Horizon 1  Enterprise Foundation      8 slices
Horizon 2  Real Data and First AI     7 slices
```

15 slices, roughly 7 months full-time. Horizon 3 is post-MVP by definition (§46).

The MVP exit criterion below and **Gate 2** in §46 are the same test stated twice.
Gate 2 is the operative version; this section explains why it is the right test.

Note what is *not* in the MVP that v0.5 included: the native Delivery Management
entities of the old Phase 3. Horizon 2 reaches the exit criterion using ingested
data and projections, not duplicated entities. If the exit criterion can be met
without building Projects, Teams, Releases, and Milestones natively, then by the
anti-scope rule below they do not belong in the MVP (see also §57.2).

## MVP exit criterion

> A Delivery Manager connects their real Jira or Azure DevOps project, opens the platform, sees which of their projects are at risk, and gets an evidence-backed explanation of **why** — with contributing factors they recognise as true.

If a Delivery Manager reads that explanation and says "yes, that's right, and I didn't know that" — the MVP has succeeded. If they say "I already knew that" or "that's wrong" — the MVP has failed regardless of how much was built.

## One persona for the MVP

v0.4 names five personas (§4). Serving five at once means serving none well. The MVP serves the **Delivery Manager** only.

Engineering Manager, Architect, SRE, and Executive are post-MVP. Their needs shape the architecture so nothing blocks them later, but no MVP feature exists for them.

## Product non-goals for the MVP

```text
Engineering Intelligence (Horizon 3, Track D)
Agentic automation and write-back (Horizon 3, Track C)
RAG / document knowledge (Horizon 3, Track B)
Model routing and multi-provider (Horizon 3, Track A)
Native Delivery Management entities (projections suffice for the MVP)
More than one integration connector
Individual developer productivity measurement — ever, per §7
Self-hosted Llama inference (measure managed models first, §11)
Executive reporting and dashboards
Mobile
Billing / subscriptions
```

## Anti-scope rule

Nothing enters the MVP unless it is required by the exit criterion above. When something feels essential, the test is: *does the Delivery Manager's "why is my project yellow?" answer get worse without it?* If not, it is post-MVP.

---

# 47. First Vertical Slice

The first slice should deliberately avoid sophisticated AI.

Target:

```text
User
 ↓
Authentication
 ↓
API
 ↓
Delivery Service
 ↓
Database
 ↓
Telemetry
 ↓
Container
 ↓
Azure
```

The goal is to prove:

* repository structure
* .NET architecture
* authentication
* service boundary
* database
* testing
* observability
* containerization
* Azure deployment
* CI/CD

Only after this works should sophisticated AI capabilities be introduced.

---

# 48. First AI Vertical Slice

After the platform foundation:

```text
Delivery Service
       ↓
AI Gateway
       ↓
Risk Analysis
       ↓
Model
       ↓
Structured Result
       ↓
Delivery Insight
```

The AI result should be:

* structured
* observable
* traceable
* cost tracked
* evaluated

---

# 49. AI Usage Rule

For every proposed AI feature:

```text
Can deterministic logic solve this?
        │
        ├── YES → Prefer deterministic logic
        │
        └── NO
             ↓
Does AI provide meaningful value?
             │
             ├── NO → Do not use AI
             │
             └── YES
                  ↓
             Evaluate:
             Quality
             Cost
             Lat​ency
             Security
             Grounding
             Observability
```

The architecture should avoid:

> **"LLM everywhere."**

AI must create measurable value.

---

# 50. Development Loop

The complete development loop is:

```text
              HUMAN
                │
                ▼
          Product Decision
                │
                ▼
             Roadmap
                │
                ▼
             Feature
                │
                ▼
            SPEC KIT
                │
          ┌─────┴─────┐
          ▼           ▼
      Specify      Clarify
          │           │
          └─────┬─────┘
                ▼
              Plan
                │
                ▼
              Tasks
                │
                ▼
        AI Coding Agent
                │
          Relevant Skills
                │
                ▼
             TDD
                │
                ▼
          Implementation
                │
                ▼
        Review / Verification
                │
                ▼
           Human Approval
                │
                ▼
             Deploy
                │
                ▼
             Feedback
                │
                └──────────────► Next Feature
```

This creates a continuous delivery loop.

---

# 51. Why Vertical Slices Matter

Vertical slices allow us to:

* validate architecture early
* discover wrong assumptions quickly
* keep the system deployable
* reduce AI context size
* reduce implementation risk
* obtain user feedback early
* measure real infrastructure behavior
* prevent large speculative implementations

The principle is:

> **Build small, working, end-to-end capabilities rather than large incomplete technical layers.**

---

# 52. Research Dimension

The project provides a practical research laboratory for:

### Software Architecture

* DDD
* distributed systems
* event-driven architecture
* service-oriented architecture
* microservices
* architecture governance

### Cloud

* Azure
* AKS
* Kubernetes
* Terraform
* identity
* networking
* platform engineering

### AI

* LLMs
* RAG
* embeddings
* agents
* tool calling
* model routing
* evaluation
* governance

### AI Economics

* model selection
* token economics
* self-hosted inference
* GPU economics
* latency
* cost optimization

### AI-Assisted Software Engineering

* specification-driven development
* AI coding agents
* custom skills
* TDD with agents
* agent verification
* automated architecture governance

---

# 53. Research Question

The deeper research question is:

> **How should enterprise software organizations operate when AI agents become part of the engineering organization?**

The project explores:

```text
Human
  +
AI Agents
  +
Engineering Process
  +
Enterprise Architecture
```

---

# 54. Two Products

The project contains two complementary products.

## Product A

### AI Engineering & Delivery Intelligence Platform

```text
.NET
Azure
AKS
Service Bus
AI
RAG
Agents
SaaS
```

## Product B

### AI-Assisted Software Engineering System

```text
Spec Kit
+
Constitution
+
ADRs
+
Custom Skills
+
Agents
+
TDD
+
Architecture Review
+
AI Evaluation
+
Verification
```

Product B builds Product A.

This creates a feedback loop:

```text
Engineering Methodology
        ↓
Build Platform
        ↓
Use Platform
        ↓
Learn
        ↓
Improve Methodology
        ↓
Build Better Platform
```

---

# 55. Immediate Action Plan

The project should begin with the following artifacts.

## Step 1 — Constitution

Create:

```text
docs/constitution.md
```

Finalize engineering rules.

---

## Step 2 — Product Vision

Create:

```text
docs/product/product-vision.md
```

Define:

* personas
* MVP
* product capabilities
* priorities

---

## Step 3 — Domain Model

Create:

```text
docs/architecture/domain-model.md
```

Define:

* bounded contexts
* entities
* aggregates
* relationships
* ownership

---

## Step 4 — System Architecture

Create:

```text
docs/architecture/system-architecture.md
```

Define:

* service boundaries
* APIs
* events
* databases
* Azure components
* security
* observability

---

## Step 5 — ADR Framework

Create:

```text
docs/adr/
```

with an ADR template.

---

## Step 6 — AI Strategy

Create:

```text
docs/ai/ai-strategy.md
docs/ai/agent-model.md
docs/ai/skill-model.md
```

---

## Step 7 — Repository Bootstrap

Create:

```text
src/
tests/
infrastructure/
deployment/
docs/
specs/
.agent/
AGENTS.md
```

---

## Step 8 — Skill Library

Create only the initial high-value skills:

```text
.agent/skills/
│
├── architecture/
├── dotnet-enterprise/
├── azure-architecture/
├── distributed-systems/
├── testing/
├── security/
└── ai-engineering/
```

Add domain skills when the corresponding domain is implemented.

---

## Step 9 — First Spec Kit Feature

Start with:

> **Authentication + Tenant Management**

This is intentionally not an AI feature.

It establishes the enterprise foundation.

---

## Step 10 — First Vertical Slice

Complete:

```text
Authentication
   ↓
Tenant
   ↓
API
   ↓
Database
   ↓
Tests
   ↓
Telemetry
   ↓
Docker
   ↓
Azure
```

Once this works:

> **We have a real platform.**

Then continue with the next slice.

---

# 56. Final Operating Model

The project should always operate according to this hierarchy:

```text
YOU
│
├── Define vision
├── Define priorities
├── Approve architecture
├── Define scope
└── Accept risk
        │
        ▼
ROADMAP
        │
        ▼
FEATURE
        │
        ▼
SPEC KIT
        │
        ├── Specify
        ├── Clarify
        ├── Plan
        └── Tasks
                │
                ▼
        AI CODING AGENT
                │
          +-----+-----+
          │           │
      Workflow      Custom
      Practices     Skills
          │           │
          +-----+-----+
                │
                ▼
             CODE
                │
             TEST
                │
             REVIEW
                │
          VERIFICATION
                │
                ▼
          HUMAN APPROVAL
                │
                ▼
             DEPLOY
```

The most important principle is:

> **You do not hand the entire project to an AI agent.**

Instead:

> **You provide intent and priorities; Spec Kit turns them into executable specifications and tasks; the agent executes small vertical slices; tests and reviews verify the result; you remain the owner of architecture, scope, and decisions.**

This allows the project to scale from a single developer using AI into a potential **multi-agent enterprise engineering system** without losing architectural control.

---

# 57. Review of v0.4 — What Changed and Why *(new in v0.5)*

This section records the critique that produced v0.5. It is kept rather than deleted, because a blueprint that hides its own revision history teaches nothing.

## 57.1 — v0.4 was a blueprint, not a specification

**Problem:** v0.4 contained no measurable outcome, no MVP boundary, and no release criterion. Its eight phases were a 12–24 month program with no definition of "done" at any level. Everything was equally mandatory, so nothing was finishable.

**Change:** added §46a — an MVP cut line (Phases 0–5), a single concrete exit criterion phrased as an observable user reaction, one MVP persona instead of five, an explicit product non-goals list, and an anti-scope rule for adjudicating future additions.

**Why one persona:** the five personas in §4 ask genuinely different questions requiring different data sources. Serving all five simultaneously produces a shallow product for each. The Delivery Manager was chosen because §6's own stated ambition — *"Why is my project yellow?"* — is that persona's question.

## 57.2 — The data-availability gap *(the most serious issue)*

**Problem:** §3 states the platform is an intelligence layer over existing systems and explicitly does not replace Jira or Azure DevOps. But v0.4's roadmap put Integration Platform nowhere in Phases 1–2, while Phase 2 built native Projects, Teams, Releases, and Milestones. Building those entities before ingesting real data leads directly to a Jira clone with worse ergonomics than Jira — contradicting §3.

Worse, every phase after 2 depends on data whose availability, shape, quality, and rate limits were never validated. Real Jira data is messy: inconsistent field usage, missing estimates, abandoned workflows, teams that don't use sprints. Discovering this in Phase 5 invalidates Phases 2–4.

**Change:** Phase 2 is now Integration & Delivery Data — one read-only connector, real tenant data, real sync failures. Native entities move to Phase 3 and are shaped by what Phase 2 proved is actually available. Added the design rule that an entity is only native if the platform adds something the source system lacks.

**The principle:** *validate data availability before building anything that depends on it.* This is the vertical-slice principle (§29) applied to data rather than to code.

## 57.3 — The AI Gateway was over-specified

**Problem:** §9 assigned the gateway eleven responsibilities and Phase 3 built all of them — with, at that point, zero consumers. §14 explicitly warns "we will not create microservices merely because we can"; the same discipline was not applied to the gateway. A router with one route is not a router.

**Change:** added §9a splitting the gateway into Stage 1 (what the first consumer needs) and Stage 2 (what a second, materially different consumer justifies), with the rule that no capability is built until a named consumer requires it. The abstraction *seam* still exists from day one — Constitution principle 9 is preserved, so callers never touch a provider directly. Only the machinery behind the seam is deferred. Phase 4 now ships the gateway and its first consumer together.

## 57.4 — AI was positioned as the scorer rather than the explainer

**Problem:** Phase 5 listed "Project Health" and "AI Recommendations" without distinguishing them, inviting an LLM into the scoring path. §49's own decision gate forbids this: whether a project is yellow is a deterministic computation over metrics, and an LLM would make it slower, costlier, and non-reproducible.

**Change:** Phase 5 now orders the work explicitly — deterministic scoring first, AI as the explanation and narrative layer over those signals. This is where AI genuinely adds value, since §6's demand for *evidence, contributing factors, forecast, and recommended actions* is a reasoning-over-context task, not a scoring task.

## 57.5 — Two products, one roadmap, no release criterion

**Problem:** §54 correctly identifies two products (the platform, and the AI-assisted engineering system that builds it) but v0.4 gave them a single roadmap. Product B's maturity was never scheduled or measured, so it risked being permanently deferred in favour of Product A features.

**Partial change:** the MVP cut line in §46a applies to Product A only. Product B's artefacts are Horizon 1 slice S1 (§46), and its improvement is driven by §54's feedback loop. In v0.6 it also gains a Horizon 3 track (Track E), which is the first time Product B appears in the roadmap as scheduled work rather than as an assumed background activity.

**Open issue:** Product B still has no success measure. A future revision should define one — a candidate is *the proportion of merged changes that passed spec → plan → tasks → implementation without a human rewriting the agent's output.* Flagged rather than resolved, because it needs real data from the first few slices before a target can be set honestly.

## 57.6 — Infrastructure cost in slice one *(considered, deliberately rejected)*

**Concern raised:** §17's target architecture — AKS, API Management, Front Door, Terraform, private endpoints — is roughly $700–1,500/month and weeks of platform work before any user-visible feature. Azure Container Apps would prove the same architectural path for a small fraction of both.

**Decision: keep §17 as written.** The owner chose to validate the real target architecture in slice one, accepting the cost and setup time in exchange for eliminating a later migration and any divergence between the blueprint and reality.

**Consequence to watch:** slice one now front-loads infrastructure ahead of user value. If the slice runs long, §57.1's cut-line discipline becomes the safeguard — the scope of *what runs on* that infrastructure must not also grow. Recorded in `specs/001-auth-tenant-management/spec.md` as Assumption 3 and flagged for reviewer attention.

## 57.7 — What v0.4 got right

Worth stating, because these are the parts v0.5 deliberately did not touch:

- **The two-product framing (§54).** Methodology building product, with a feedback loop between them, is the genuinely original idea here.
- **The source-of-truth hierarchy (§42),** and specifically that ADRs beat skills and that an agent must *propose* an ADR change rather than silently override one. This is the single most important safeguard in the document.
- **The vertical-slice principle (§29)** and the insistence that slice one contain no AI (§47). Resisting the temptation to lead with the interesting part is a sign of engineering maturity.
- **The AI usage gate (§49)** and its explicit rejection of "LLM everywhere."
- **§7's refusal to rank individual developers.** Measuring engineering systems rather than people is both ethically correct and better engineering.
- **§35 — tasks are not a blind to-do list.** Correct, and the reason this review exists at all.

---

# 58. Immediate Next Steps *(updated in v0.6)*

Horizon 1, slice S1 is partly done. What remains before any code is written:

```text
DONE  Engineering Constitution     .specify/memory/constitution.md   v1.0.0, 11 principles
DONE  Feature spec for S2          specs/001-auth-tenant-management/

1. ADR framework + template        docs/adr/                         (§45)
2. ADR-001  Azure-first                                              (Constraints)
3. ADR-002  .NET-first                                               (Constraints)
4. ADR-003  Service-oriented architecture                            (Principle III)
5. ADR-007  AKS in Horizon 1, not deferred                           (§57.6, §59.1)
6. ADR-008  AI Gateway staged, seam-first                            (§9a, Principle IX)
7. ADR-009  Capability-based model abstraction                       (Principle IX)
8. Narrow spec 001 to slice S2 only                                  (§59.3)
9. /speckit.plan on 001
10. /speckit.tasks on 001
11. Initial skills                 .agent/skills/ — 7 only           (§55 Step 8)
```

Steps 1–7 precede step 9, because the plan must cite architectural authority and
the constitution's Principle Gate Checklist requires ADRs to exist to be checked
against. Step 8 precedes step 9 for the reason given in §59.3.

Note the constitution lives at `.specify/memory/constitution.md`, not
`docs/constitution.md` as §43 and §55 anticipated, because that is where the
tooling reads it from. A pointer at `docs/constitution.md` would be reasonable;
two copies would not.


---

# 59. Why Three Horizons — and the Cost of Research-First *(new in v0.6)*

## 59.1 — The phase structure was the problem, not the phase content

v0.5's eight phases were individually defensible and collectively unusable. The
defect was structural: **a phase has no exit condition.** "Phase 2 — Integration"
is done when someone declares it done. So every phase stayed open, every phase
was equally mandatory, and the plan totalled ~52 slices — 12–24 months — with no
point at which anything could be reconsidered.

Horizons fix this by pairing each with a gate. A gate is not a milestone or a
celebration; it is a **question that can be answered wrongly.** Gate 2 in
particular is designed to be failable: if a real Delivery Manager reads a real
risk explanation and says *"I already knew that,"* the product premise is falsified
and everything in Horizon 3 would have rested on it. Discovering that at month 7
costs 7 months. Discovering it at month 24 costs the project.

The committed plan is now **15 slices, roughly 7 months.** Horizon 3 exists as a
menu rather than a sequence because its correct ordering is genuinely unknowable
until Gate 2 has been answered.

## 59.2 — Research-first is a real choice with a real price

**Decision: when breadth of technology and speed to user value conflict, breadth
wins.**

The alternative was considered. A product-first Horizon 1 — Azure Container Apps
instead of AKS, no Service Bus, no private endpoints — reaches a deployed,
observable, multi-tenant application in roughly 4 weeks rather than 12–14. That
is a saving of about two months, and it was declined deliberately.

**What the price buys:** genuine operational experience of the enterprise stack.
Not "I read about AKS" but "I have debugged an AKS rollout, provisioned it from
Terraform into an empty subscription, and connected it through private endpoints."
Given that §52 and §53 make this project explicitly a research laboratory, and
§53 asks how enterprise organisations should operate when AI agents join the
engineering team, answering that question on a stack that is not enterprise-shaped
would produce findings that do not transfer.

**The failure mode this creates, and the safeguard against it.** Research-first
degrades in a specific way: technologies get stood up, demonstrated once on the
happy path, and never driven hard. That produces the *illusion* of experience,
which is worse than no experience because it is indistinguishable from the real
thing until something breaks in production.

The safeguard is therefore binding, and Gate 1 enforces it:

> Every technology adopted MUST be exercised by a real capability under real
> failure conditions before the horizon containing it is considered complete.

Concretely — Service Bus is not learned until a duplicate message has been handled
idempotently and a dead-lettered message replayed. AKS is not learned until a
rollout has failed and been recovered. Multi-tenancy is not learned until an
automated test has caught an attempted cross-tenant read. This is why Gate 1's
checklist names failure scenarios rather than deployments.

## 59.3 — Spec 001 is currently a phase, not a slice

Feature 001 as written spans what §30 correctly separated into slices S2, S4, S5,
S6, and S7: authentication and tenancy *plus* observability, containerization,
Terraform, and CI/CD. Its Story 4 alone contains the entire Azure delivery path.

This happened as a direct consequence of the AKS decision — Terraform and CI/CD
stop being separable when the first deployment must provision AKS, APIM, Key
Vault, and private endpoints. The consequence is nonetheless real: **spec 001 is a
large incomplete technical layer, which is exactly what §29 prohibits.**

Recommended correction, recorded here rather than silently applied because it
changes an approved specification (Principle II):

```text
Spec 001  narrow to Stories 1–3  → slice S2, locally verifiable, ~2 weeks
Spec 002  Story 4's telemetry     → slice S4
Spec 003  Story 4's container      → slice S5
Spec 004  Story 4's Terraform/AKS  → slice S6
Spec 005  Story 4's CI/CD          → slice S7
```

Stories 1–3 are already written as independently testable, which is what makes
this split cheap. The Gate 1 checklist is unaffected — it still requires all of
S2–S8 to have passed, so nothing is dropped, only sequenced.

## 59.4 — What v0.6 did not change

- **§17's target architecture.** Unchanged, and now explicitly justified by
  §59.2 rather than merely asserted.
- **§46a's single persona and the Delivery Manager exit criterion.** These were
  the strongest parts of v0.5 and survive intact; Gate 2 is that criterion made
  operative.
- **§57 in full.** The v0.5 review is retained. Its §57.2 integration-first
  argument is now embodied in Horizon 2's ordering, and its §57.6 concern about
  front-loaded infrastructure is now answered by an explicit decision rather
  than left as a flagged risk.
- **The eight-phase capability content.** Nothing was deleted. Every capability
  from v0.5's Phases 2–8 appears in Horizon 2 or in a Horizon 3 track. The
  change is to commitment and sequencing, not to ambition.
