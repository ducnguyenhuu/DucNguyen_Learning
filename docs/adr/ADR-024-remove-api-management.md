# ADR-024: Remove API Management; Front Door fronts Container Apps directly

**Status**: Accepted
**Date**: 2026-10-20
**Deciders**: Project owner
**Relates to**: ADR-007 (refines — edge topology only) · ADR-023 · ADR-001 · ADR-012 · Constitution → Principle X · `idea.md` §17 · roadmap S6

## Context

ADR-007 built the full `idea.md` §17 edge in Horizon 1: Front Door → API Management → compute.
API Management (Developer tier) is the largest fixed cost in the S6 environment (about $50 a
month) and the slowest resource to provision (30–45 minutes per apply, which dominates every
iteration of the apply/destroy cycle). Nothing in Horizon 1 consumes what APIM adds — no
subscription keys, no per-consumer policies, no request transformation, no developer portal.
The API's only caller-facing contract is its Entra ID bearer token, validated by the API itself.

The project is a research exercise run in short, paid sessions with `terraform destroy` between
them, so both the money and the wait matter. The owner decided APIM is not needed.

## Decision

1. **API Management is not provisioned.** The edge is `Front Door → Container Apps`.
2. **The Front Door origin is the container app's ingress FQDN.** The `apim` Terraform module,
   the `sn-apim` subnet and the `apim_sku` variable are deleted.
3. **The container app's ingress is public with no source restriction.** The IP allow-list existed
   only to let APIM's outbound addresses in; Front Door's backend addresses are a service tag,
   which Container Apps ingress restrictions cannot express. Every endpoint except the health
   probes still requires a valid Entra token and an explicit authorization policy (ADR-022), so
   the exposure is the health endpoints, which return no data.
4. **Minimum replicas default to 1.** Single revision mode keeps the previous revision serving
   until the new one is healthy, so zero-dropped-traffic does not need a second replica
   (spec 005 FR-014 amended).

## Consequences

### Positive

- About $50 a month less when the environment is up, and applies drop from 30–45 minutes to a
  few minutes for the same topology.
- One fewer moving part to debug; the S7 load test and the pipeline's deploy path are unchanged.

### Negative

- Direct access to the container app's `*.azurecontainerapps.io` address bypasses Front Door
  (and therefore any future WAF). Accepted for a dev environment.
- No place to hang gateway policies (rate limiting, key-based access, request transformation).
  The research value of learning APIM is given up deliberately.

### Revisit When

- A consumer needs gateway features (per-client quotas, subscription keys, transformation), or
- Front Door should be the only way in: either enforce the `X-Azure-FDID` header in the API, or
  move to Front Door Premium with Private Link to an internal Container Apps environment.

## Alternatives Considered

### APIM Consumption tier

About $0 idle and minutes to provision, but it has no fixed outbound IPs, so the origin
restriction would still need replacing, and nothing consumes APIM's features anyway.

### Keep APIM Developer

Rejected: fixed cost and apply time with no consumer (Principle X).
