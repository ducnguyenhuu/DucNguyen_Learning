# ADR-001: Azure as the primary cloud

**Status**: Accepted
**Date**: 2026-08-08
**Deciders**: Project owner
**Relates to**: Constitution → Technology Constraints · `idea.md` §13, §17, §44 item 1

## Context

The platform is an enterprise SaaS product targeting software organisations, and it
is simultaneously a research vehicle for how AI agents participate in enterprise
engineering (`idea.md` §52–53). Both objectives need a cloud, and the choice
constrains nearly everything downstream: identity, messaging, data, secrets,
observability, and the deployment model.

Two forces dominate. First, the target customer profile — enterprise engineering
organisations using Jira, Azure DevOps, and Microsoft identity — skews heavily
Microsoft. Azure DevOps integration is a first-class requirement (roadmap S9), and
Microsoft Entra ID is the assumed identity provider. Second, the research objective
in §53 asks how *enterprise* organisations should operate; answering that on a stack
enterprises do not use would produce findings that do not transfer.

There is no existing infrastructure to preserve, so this is a genuinely open choice
rather than a ratification of the status quo.

## Decision

We use **Microsoft Azure** as the primary and default cloud provider. All
infrastructure is provisioned in Azure unless a specific ADR grants an exception.

Concretely this settles: AKS for orchestration, Azure SQL for relational data,
Azure Service Bus for messaging, Microsoft Entra ID for identity, Azure Key Vault
for secrets, and Azure Monitor / Application Insights as the telemetry backend.

Adopting a non-Azure service requires its own ADR stating why the Azure equivalent
is insufficient.

## Consequences

### Positive

- Identity, secrets, and workload identity integrate natively, which is what makes
  Constitution Principle V's prohibition on stored credentials practical rather than
  aspirational.
- Azure DevOps integration (roadmap S9) sits inside the same identity and tenancy
  model as the platform itself.
- One provider means one set of idioms to learn deeply rather than several
  shallowly — which serves the research objective better than breadth would.

### Negative

- **Vendor coupling is real and largely accepted.** Service Bus semantics, Entra ID
  token shapes, and managed identity are not portable. Moving clouds later would be
  a rewrite of the infrastructure and integration layers, not a reconfiguration.
- Azure's Kubernetes and API Management experience is generally regarded as rougher
  than some competitors'. Roadmap S6 budgets 3–4 weeks partly for this.
- Cost transparency in Azure is poor at small scale, which makes the ~$700–1,500
  monthly estimate in ADR-007 less certain than we would like.

### Neutral / accepted trade-offs

- The AI provider does not have to be Azure OpenAI. ADR-009 keeps model selection
  behind a capability abstraction precisely so that this decision does not silently
  determine the model strategy.
- Azure-first does not mean Azure-only for *development*. Local development uses
  containers (roadmap S5) and does not require a subscription.

## Alternatives Considered

### AWS

The largest and most mature provider, with the strongest managed-service breadth. It
was rejected primarily on identity: the platform assumes Entra ID for authentication
and tenant membership, and the target customers' engineering systems are
Microsoft-centric. Running Entra ID identity against AWS infrastructure adds a
federation seam at the most security-sensitive point in the system for no
corresponding benefit. AWS's .NET support is competent but is not where .NET is most
at home.

### Google Cloud

Strongest Kubernetes experience of the three, and GKE would have made roadmap S6
materially easier. Rejected for the same identity reason as AWS, plus the weakest
alignment with the enterprise .NET and Azure DevOps ecosystem the product integrates
with.

### Multi-cloud from the start

Rejected without much hesitation. Multi-cloud at this stage would mean abstracting
messaging, identity, secrets, and data behind portability layers before a single
customer exists — the speculative generality that Constitution Principle III and
ADR-008 both reject. It would roughly double roadmap S6 and deliver portability that
nobody has asked for.

## Revisit When

- A prospective customer requires deployment in a cloud we do not support, and the
  deal is large enough to fund the port.
- Azure costs for the Horizon 1 footprint exceed roughly $2,000/month without a
  corresponding increase in delivered value.
- A materially better AI or data service appears elsewhere and ADR-009's abstraction
  proves insufficient to reach it.

## Compliance

Enforced by review, not automation — this is a provisioning-time decision and
Terraform (ADR-012) is where it manifests. The practical gate is that all
infrastructure is defined in Terraform under `infrastructure/`, so a non-Azure
resource would appear in a pull request diff as a new provider block, which is
conspicuous.

**Known weakness:** no automated gate prevents a developer from calling a non-Azure
managed service directly from application code. If this becomes a real risk, an
architecture test restricting outbound SDK dependencies would close it.
