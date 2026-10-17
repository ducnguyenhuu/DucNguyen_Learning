# System Architecture

**This document is a navigational index, not a second source of truth.** `idea.md` §55
Step 4 asked for a system architecture document. Most of the content already exists in
`idea.md` and the ADRs; duplicating it would violate Constitution Principle II. What is
genuinely new here is the **deviation table** at the end.

See [traceability U1](../traceability.md#u1--55-steps-2-4-and-6-require-five-documents-that-roadmap-s1-does-not-list).

## Target runtime topology

```text
Azure Front Door
       ↓
Azure API Management
       ↓
  Container Apps
       ↓
+------+-------+----------------+
|              |                |
Services       Workers          AI
|              |                |
+--------------+----------------+
       ↓
+------+-------+---------+
|              |         |
Azure SQL   Service   Storage
            Bus
```

Full detail in `idea.md` §17. Provisioned by Terraform (ADR-012) in slice 6, per
ADR-007 (compute platform: Container Apps, per ADR-023).

## Where each concern is decided

| Concern | Authority |
|---------|-----------|
| Cloud | [ADR-001](../adr/ADR-001-azure-first.md) |
| Language and runtime | [ADR-002](../adr/ADR-002-dotnet-first.md) |
| **Service boundaries and data ownership** | [ADR-003](../adr/ADR-003-service-oriented-architecture.md) |
| Why the full topology in Horizon 1 | [ADR-007](../adr/ADR-007-aks-in-horizon-1.md) |
| Compute platform (Container Apps, not AKS) | [ADR-023](../adr/ADR-023-azure-container-apps-for-compute.md) |
| AI gateway staging | [ADR-008](../adr/ADR-008-ai-gateway-staged.md) |
| Model abstraction | [ADR-009](../adr/ADR-009-capability-based-model-abstraction.md) |
| Instrumentation | [ADR-011](../adr/ADR-011-opentelemetry.md) |
| Infrastructure as code | [ADR-012](../adr/ADR-012-terraform.md) |
| **Multi-tenancy model** | [ADR-013](../adr/ADR-013-multi-tenancy-model.md) |
| Bounded contexts, aggregates | [domain-model.md](domain-model.md) |
| Security principles | `idea.md` §18 · Constitution Principles IV, V |
| Observability requirements | `idea.md` §20 · Constitution Principle VI |
| Distributed-systems behaviour | `idea.md` §21 · Constitution Principle VII |
| Testing strategy | `idea.md` §22 · Constitution Principle VII |
| Events | `idea.md` §16 · domain-model.md |
| APIs | Per-slice feature specs under [specs/](../../specs/) |

## Services

Four, per ADR-003 — **created by the slice that needs them, not up front.**

| Service | Owns its database | Slice |
|---------|------------------|-------|
| Platform / Tenancy | tenants, users, memberships, invitations | 2 |
| Integration | connections, sync state, raw payloads | 9 |
| Delivery | canonical work data, health scores, risks | 11 |
| AI Platform | capabilities, prompts, invocations, costs | 13 |

Cross-service database access is prohibited without exception (Principle III).
Communication is by API, event, or message only.

## Deviations from `idea.md` §17

The one thing in this document that is not recorded elsewhere. Each deviation is
deliberate.

| §17 component | Status | Why |
|---------------|--------|-----|
| **Azure AI Search** | **Not provisioned** | No consumer until Horizon 3 Track B. Provisioning it in slice 6 would pay for an idle service for months, violating Principle X. [traceability U2](../traceability.md#u2--17-provisions-ai-search-which-nothing-uses-until-horizon-3) |
| Storage | Deferred | No consumer until documents exist (Track B). |
| QA environment | Deferred | `idea.md` §23 shows Dev → QA → Prod. Slice 7 builds Dev only; a QA environment with no users and no release process is cost without function. [traceability U7](../traceability.md#u7--23s-pipeline-includes-a-qa-environment-roadmap-s7-has-only-dev) |
| Production environment | Deferred | Post-Gate-1. Human approval gate is built in slice 7; the environment is not. |
| Agent Runtime (§8) | Not in either gateway stage | No consumer until Track C. See ADR-008. |
| **AKS** | **Replaced by Container Apps** | Operating complexity outweighs Kubernetes learning value in Horizon 1. [ADR-023](../adr/ADR-023-azure-container-apps-for-compute.md) |

`idea.md` §17 itself is unamended, so it still describes the full target. These are
scheduling decisions, not changes of direction.
