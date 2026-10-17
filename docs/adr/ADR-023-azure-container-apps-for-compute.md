# ADR-023: Azure Container Apps as the compute platform, in place of AKS

**Status**: Accepted
**Date**: 2026-10-16
**Deciders**: Project owner
**Relates to**: ADR-007 (refines — compute clause only) · ADR-001 · ADR-012 · ADR-018 · Constitution → Technology Constraints, Principle X · `idea.md` §17, §52, §59.2 · roadmap S6

## Context

ADR-007 chose to build the full `idea.md` §17 topology in Horizon 1, with AKS as the
compute layer, and explicitly rejected Azure Container Apps as "the fallback if S6
overruns badly". It recorded a trigger for revisiting: S6 over 6 weeks, spend over
~$2,000/month, or Gate 2 slipping past roughly month 9. **None of those triggers has
fired.** This ADR is not the fallback being invoked under pressure.

It is a deliberate change of mind by the owner, made after the S6 code was written
(branch `005-terraform-azure`, code-only, never applied). The reason is operating
complexity: AKS brings node pools, NGINX ingress, the Key Vault CSI driver, workload
identity federation into a cluster, Helm, and pod and rollout debugging — a large
surface for a single-service, single-developer Horizon 1. Most of that surface is
Kubernetes itself rather than the enterprise topology the project set out to study.

ADR-007's research argument was that Container Apps "abstracts away exactly the things
the research objective wants to learn". That remains true, and this ADR does not claim
otherwise. What it weighs is whether those things are worth their cost *now*, ahead of
any consumer that needs them (Principle X).

## Decision

**Compute runs on Azure Container Apps**, in a VNet-integrated Container Apps
environment, in place of AKS.

Everything else in ADR-007's topology is unchanged:

```
Front Door → API Management → Container Apps → Azure SQL / Service Bus
                                                Key Vault
                                        OTel Collector → New Relic (OTLP)
              Managed identity + private endpoints throughout
```

Specifically, the following carry over as-is:

- API Management, Front Door, Azure SQL, Key Vault, ACR, private endpoints.
- Terraform for everything (ADR-012), one `dev` environment, `terraform destroy`
  between sessions, provisioning into an empty subscription as S6's proof.
- No stored credentials (Principle V). The mechanism changes from AKS workload identity
  federation to a **user-assigned managed identity** attached to the container app,
  used for ACR pull, Key Vault, and SQL.
- OpenTelemetry Collector → New Relic (ADR-018). The Collector runs as a **sidecar
  container in the same container app**, not a separate cluster workload.
- The SIGTERM/health/non-root contract from S5 is the contract Container Apps probes
  rely on. The image does not change.

Mapping of the AKS concepts S6 was going to exercise:

| AKS | Container Apps |
|-----|----------------|
| Deployment rollout | Revision |
| Readiness / liveness probes | Same probes, configured on the revision |
| Failed rollout keeps old pods serving | Failed revision never receives traffic; previous revision keeps serving |
| `kubectl rollout undo` | Redeploy the previous known-good image tag (single revision mode; a failed revision never took traffic) |
| NGINX ingress | Built-in ingress (internal to the VNet; APIM is the only front) |
| Key Vault CSI + workload identity | Key Vault secret reference via managed identity |
| Helm chart | Terraform (`azurerm_container_app`) — no separate deploy tool |

Because the application is now a Terraform resource, **ADR-012's split — Terraform
provisions, Helm deploys — no longer applies.** The container app definition lives in
Terraform; the CI/CD pipeline (S7) updates the image tag on it.

## Consequences

### Positive

- Far less to operate and debug. No cluster, node pool, ingress controller, CSI driver,
  or Helm chart. S6's unknown-unknowns shrink to APIM and private endpoint wiring.
- Compute cost is near zero while idle (consumption plan, free monthly grant,
  scale-to-zero available), instead of always-on node VMs.
- The S6 "rollout deliberately broken and recovered" proof survives intact in revision
  form: a bad revision is deployed, fails its probes, never takes traffic, and traffic
  is replaced by redeploying the known-good tag.
- The container image, Dockerfile, compose stack, and telemetry design from S3–S5 are
  untouched.
- Container Apps is built on Kubernetes (and KEDA/Dapr), so the container-deployment
  concepts transfer partly if AKS is adopted later.

### Negative

- **Kubernetes is no longer learned in Horizon 1.** `idea.md` §52 lists AKS and
  Kubernetes as explicit research targets; they are now deferred, not delivered. The
  roadmap line "AKS is not learned until a rollout has failed" and Gate 1's matching box
  are reworded to revisions. They do not claim Kubernetes experience.
- Less control: no custom schedulers, service mesh, node-level tuning, or arbitrary
  Kubernetes resources. Some future workloads (the Agent Runtime, §8) may need it.
- Re-platforming to AKS later, if it is ever needed, is real work. It is smaller than
  ADR-007 feared because the image and Terraform discipline carry over, but it is not
  free.
- The S6 code already written on `005-terraform-azure` (AKS, Helm chart, NGINX ingress,
  CSI wiring) is largely discarded and its compute layer rewritten. Specs under
  `specs/005-terraform-azure/` must be revised to match.

### Neutral / accepted trade-offs

- **Cost is no longer dominated by compute.** API Management (Developer tier), Front
  Door, and private endpoints now account for most of the bill. The ~$700–1,500/month in
  ADR-007 should be replaced by a fresh estimate when the S6 plan is revised; the figure
  here is deliberately not restated until it is checked against the Azure pricing
  calculator. Those three components are the next place to look if cost is still too
  high.
- ACR private endpoint requires the Premium SKU. Whether that is worth it in `dev` is a
  plan-time decision for S6.
- Container Apps ingress is HTTP/HTTPS. This matches every workload in the roadmap;
  Service Bus workers (S8) run as non-ingress container apps.

## Alternatives Considered

### Stay on AKS (ADR-007 as written)

Maximum research value and the original owner decision. Rejected here on complexity and
on the argument above that Kubernetes depth has no consumer in Horizon 1. Remains valid
if the research objective is later re-weighted.

### Azure App Service for Containers

Rejected, as in ADR-007. It would be simpler to run, but it has no revision/traffic model
to carry the failed-rollout proof, scales less flexibly, and its networking model is
further from the target topology.

### Drop APIM and Front Door as well, ingress directly to Container Apps

The largest remaining cost saving. Not taken: this ADR changes only the compute
platform. APIM and Front Door are the edge topology §17 describes and the S7 pipeline
and S6 proof list refer to them. Reconsider if cost remains the problem.

## Revisit When

- A workload needs Kubernetes capabilities Container Apps does not offer (custom
  controllers, service mesh, GPU scheduling for the Agent Runtime, strict node-level
  isolation).
- The research objective is re-weighted so that Kubernetes depth is wanted again.
- Container Apps limits (scale, networking, private endpoint behaviour) block a roadmap
  slice.

## Compliance

- Terraform only (ADR-012). The container app, environment, identity, and revisions are
  all declared in code.
- S6 proof is unchanged in spirit: empty-subscription apply, health through Front Door
  and APIM, managed identity to SQL and Key Vault, New Relic traces, a deliberately
  broken and recovered revision, clean destroy.
- This changes a Technology Constraint, which the Constitution allows by ADR without
  amendment. The Constitution's "Orchestration" bullet still names AKS and is now stale;
  per its Amendment Process only a human maintainer may edit it.
