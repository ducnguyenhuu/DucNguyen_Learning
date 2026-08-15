# ADR-007: AKS and the full target architecture in Horizon 1, not deferred

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: `idea.md` §17, §57.6, §59.2 · roadmap S6 · Constitution Principle X

## Context

`idea.md` §17 defines the target runtime architecture: Azure Front Door → API
Management → AKS → Azure SQL / Service Bus / Storage, with Key Vault, managed
identity, and private endpoints. The question this ADR settles is **when** that
architecture is built, not whether.

Two positions were argued.

A lighter start was proposed and argued for explicitly during planning: Azure
Container Apps plus Azure SQL would prove the same end-to-end path — identity, API,
service, database, telemetry, container, cloud, pipeline — in roughly 4 weeks instead
of 12–14, at perhaps $50–100/month instead of $700–1,500. The same container images
would later migrate to AKS when scale or multi-workload needs actually demanded it.
Constitution Principle X's prohibition on building for anticipated future needs
arguably favours this.

The counter-position is the project's research objective. `idea.md` §52–53 make this
explicitly a laboratory for enterprise architecture, and §53 asks how *enterprise*
organisations should operate when AI agents join engineering teams. Container Apps is
a fine product but it is not the enterprise topology; findings from it would not
transfer to the question being asked.

The owner chose the second position. This ADR records that choice and its price
honestly, because the alternative was genuinely reasonable and in six months it will
matter whether the reasoning was sound.

## Decision

We build the **full `idea.md` §17 architecture in Horizon 1, at roadmap slice S6**:
AKS, API Management, Front Door, Azure SQL, Key Vault, managed identity and workload
identity federation, private endpoints, and Log Analytics — all provisioned by
Terraform (ADR-012).

We do **not** use an intermediate hosting platform and migrate later.

Slice S6 is budgeted at **3–4 weeks** and is explicitly the largest single slice in
the roadmap.

## Consequences

### Positive

- No migration step. The architecture proven in Horizon 1 is the architecture that
  runs in production, so there is no later project to re-platform.
- No divergence between the blueprint and reality, which keeps `idea.md` §17
  trustworthy as documentation rather than aspiration.
- Real operational experience of the enterprise stack — AKS, APIM, private
  networking, workload identity — which is the primary deliverable of the research
  objective. This is what the money and time actually buy.
- Private endpoints and managed identity from the start means Principle V's
  prohibition on stored credentials is never violated and then retrofitted.

### Negative

- **Roughly 8–10 weeks of additional elapsed time before any user-visible feature
  exists.** This is the dominant cost and it is not recoverable.
- **~$700–1,500/month** at standard SKUs, beginning at S6 and continuing indefinitely.
- Horizon 1 front-loads infrastructure ahead of product value, which is the shape
  `idea.md` §29 warns against. The mitigation is that Gate 1 is a hard stop, so the
  infrastructure cannot expand further without the product following.
- Higher risk of the slice overrunning. AKS, APIM, and private endpoint
  interactions are where most of the unknown-unknowns in this project live.
- Debugging surface is much larger during S2–S5, so local development must stay
  genuinely local (see trade-offs).

### Neutral / accepted trade-offs

- **Slices S2 through S5 must remain runnable and verifiable without Azure.** This is
  a direct consequence: if the only way to test is to deploy, the 3–4 week slice
  becomes a 3–4 week blocker on everything. Spec 001 was narrowed specifically so
  that S2 needs no Azure subscription.
- Dev/test SKUs and `terraform destroy` between working sessions are expected
  practice, not a fallback. Roadmap S6's proof list requires provisioning into an
  empty subscription precisely so that tearing down is safe.
- One environment (`dev`) only in Horizon 1. QA and production wait.

## Alternatives Considered

### Azure Container Apps first, AKS later

The strongest alternative, argued for explicitly and rejected by the owner.

**For:** ~4 weeks instead of 12–14. ~$50–100/month instead of $700–1,500. Same
containers, same code, same Terraform discipline. Proves identity, API, data,
telemetry, container, and pipeline end to end. Reaches Gate 1's *product* criteria
faster, leaving more calendar time for Horizon 2 where the actual value is.

**Against, and why it lost:** Container Apps abstracts away exactly the things the
research objective wants to learn — pod scheduling, ingress topology, service mesh
concerns, private endpoint wiring, workload identity federation into a cluster. A
platform engineer who has only used Container Apps has not learned AKS. Since
`idea.md` §52 lists AKS, Kubernetes, and platform engineering as explicit research
targets, deferring them defers the point.

Recorded here because if S6 overruns badly, this is the fallback, and the reasoning
should not have to be reconstructed under pressure.

### App Service

Rejected quickly. Simpler than Container Apps in some respects but further still from
the target topology, and its scaling and networking model would not transfer.

### Local Kubernetes (kind / minikube) then Azure later

Would teach Kubernetes concepts cheaply. Rejected because the genuinely difficult and
genuinely enterprise parts — APIM integration, private endpoints, workload identity
federation, Azure networking — are exactly what a local cluster cannot teach. The easy
half would be learned and the hard half deferred.

## Revisit When

- **S6 exceeds 6 weeks.** At that point the Container Apps fallback above should be
  reconsidered seriously rather than pushing through on sunk cost.
- Monthly Azure spend exceeds ~$2,000 without corresponding value.
- Gate 1 is reached but Horizon 2 is delayed such that Gate 2 slips past roughly
  month 9 — the product premise stays unfalsified for too long, which is the risk
  §59.1 exists to manage.

## Compliance

- All of it is Terraform (ADR-012); no manual portal configuration is permitted, and
  roadmap S6's proof requires provisioning into an *empty* subscription to demonstrate
  this.
- Roadmap S6 proof includes a deliberately broken and recovered rollout, per
  `idea.md` §59.2's safeguard — AKS is not considered learned until this has happened.
- Gate 1 blocks Horizon 2 until the environment provisions from code alone.
