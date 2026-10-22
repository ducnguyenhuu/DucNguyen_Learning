# ADR-012: Terraform for all infrastructure

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Technology Constraints, Principle X · `idea.md` §13, §17, §44 item 7 · roadmap S6
**Refined by**: [ADR-023](ADR-023-azure-container-apps-for-compute.md) (2026-10-16) — compute is Container
Apps, so the container app is a Terraform resource and the "Terraform provisions, Helm deploys" split below
no longer applies. Read AKS as Container Apps and ignore the ADR-007 cost figure.

## Context

ADR-007 commits to provisioning the full `idea.md` §17 architecture in Horizon 1: AKS,
API Management, Front Door, Azure SQL, Key Vault, managed identity, private endpoints,
and Log Analytics. That is a large amount of infrastructure with intricate
interdependencies — particularly the private networking and workload identity
federation wiring.

Two requirements constrain how it is defined. Constitution Principle X requires
infrastructure to be *reproducible into a clean environment with no manual
configuration*, and roadmap S6's proof demands provisioning into an **empty**
subscription from code alone. Both exist so that tearing the environment down between
working sessions is safe — which, given ADR-007's ~$700–1,500/month cost, is a
practical necessity rather than a nicety.

## Decision

We define **all infrastructure as Terraform**, in `infrastructure/terraform/`, with
remote state in Azure Storage.

**Manual portal configuration is prohibited.** Any resource or setting that exists only
because someone clicked it in the portal is a defect, because it makes the environment
irreproducible and silently breaks the teardown/rebuild cycle.

Structure: reusable modules per concern, composed per environment. Horizon 1 has one
environment (`dev`). QA and production are added when the roadmap reaches them, and
must reuse the same modules rather than copying them.

Kubernetes workload manifests are **not** Terraform's responsibility — Helm or plain
manifests under `deployment/` handle application deployment. Terraform provisions the
cluster; it does not deploy the application to it.

## Consequences

### Positive

- The environment is reproducible, which is what makes `terraform destroy` between
  sessions a cost-control tool rather than an act of faith.
- Infrastructure change is reviewable in a pull request diff, and `terraform plan`
  makes the intended change explicit before it is applied.
- Drift is detectable. Something changed in the portal shows up as a plan diff.
- Provider-agnostic tooling, which slightly hedges ADR-001's vendor coupling — the
  HCL structure and module discipline transfer even though the resources do not.

### Negative

- **State management is a genuine operational burden and a genuine hazard.** Remote
  state must be provisioned before Terraform can use it (a bootstrap step outside
  Terraform), must be locked to prevent concurrent applies, and must be backed up. A
  corrupted or lost state file is a serious incident.
- Terraform's Azure provider lags Azure feature releases. Occasionally a resource must
  be handled by `azapi` or accepted as unsupported until the provider catches up.
- Long apply times for AKS and API Management — APIM in particular can take 30–45
  minutes — which makes the S6 iteration loop slow and is part of why that slice is
  budgeted at 3–4 weeks.
- Some resources resist clean destruction (soft-deleted Key Vaults, APIM name
  reservations), so "destroy and rebuild" is not always as clean as intended.

### Neutral / accepted trade-offs

- The remote state backend itself is created by a small bootstrap script, not by
  Terraform. This is the one accepted exception to "no manual setup", and it should be
  scripted and committed so it is still reproducible.
- Secrets are never in Terraform variables or state. Key Vault is provisioned by
  Terraform; its *contents* are not managed by Terraform (Principle V).
- Terraform manages infrastructure only. Application configuration and deployment are
  separate concerns, deliberately.

## Alternatives Considered

### Bicep / ARM templates

The native Azure choice, with immediate support for new Azure features, no state file
to manage (ARM is the state), and good tooling. Genuinely the strongest alternative
given ADR-001's Azure commitment, and it would eliminate the state-management burden
listed above.

Rejected on transferable skill and ecosystem. `idea.md` §52 lists Terraform explicitly
as a research target, Terraform is the broader industry standard, and its module
ecosystem for AKS and networking is more mature. This is a case where the research
objective legitimately outweighed the local optimum — recorded plainly so that if the
state burden becomes painful, the trade-off is visible rather than mysterious.

### Pulumi

Infrastructure in C#, which would align with ADR-002 and allow sharing types with the
application. Attractive on paper. Rejected because general-purpose languages make it
too easy to write infrastructure with logic in it, which undermines the
reviewability that is the main point of infrastructure-as-code; and because the
ecosystem and hiring pool are smaller.

### Azure portal plus documentation

Rejected outright. It violates Principle X, makes S6's proof impossible, and makes
teardown-and-rebuild unsafe — which under ADR-007's cost profile would mean either
paying continuously or risking an unreproducible environment.

## Revisit When

- The Azure provider blocks a needed feature for a sustained period.
- State management causes a serious incident, which would make Bicep's stateless model
  look considerably better.
- Multi-environment composition becomes unwieldy, which is a signal to restructure
  modules rather than to change tools.

## Compliance

- **Roadmap S6 proof:** `terraform apply` into an *empty* subscription produces a
  working environment with zero manual portal configuration.
- **Roadmap S6 proof:** `terraform destroy` cleanly removes everything.
- **Gate 1:** the whole environment provisions from code alone.
- **Roadmap S7:** the pipeline runs `terraform plan` on pull requests, so
  infrastructure change is visible before merge.

**Known weakness:** nothing prevents someone from changing a setting in the portal. The
detection mechanism is drift appearing in the next `terraform plan`, which is reactive
rather than preventive. Restricting human write access to the subscription and
requiring changes through the pipeline identity would close this properly, and is worth
doing in S7.
