---
name: azure-architecture
description: Use when touching infrastructure, provisioning Azure resources, writing Terraform, or working on Container Apps deployment, identity, or networking.
---

# Azure Architecture

Decisions: [ADR-001](../../../docs/adr/ADR-001-azure-first.md) (Azure),
[ADR-007](../../../docs/adr/ADR-007-aks-in-horizon-1.md) (full topology in Horizon 1),
[ADR-023](../../../docs/adr/ADR-023-azure-container-apps-for-compute.md) (Container Apps, not AKS),
[ADR-012](../../../docs/adr/ADR-012-terraform.md) (Terraform).

## The absolute rule

**No manual portal configuration.** Anything that exists only because someone clicked it
is a defect — it makes the environment irreproducible and silently breaks the
teardown/rebuild cycle that keeps cost under control.

Slice 6's proof: `terraform apply` into an **empty** subscription produces a working
environment, and `terraform destroy` cleanly removes it.

## Target topology (slice 6)

```
Front Door → API Management → Container Apps → Azure SQL / Service Bus
                                     Key Vault
                               OTel Collector → New Relic (OTLP)
                              Managed identity + private endpoints throughout
```

**Telemetry leaves Azure.** [ADR-018](../../../docs/adr/ADR-018-new-relic-telemetry-backend.md)
makes New Relic the default backend over OTLP — the one granted exception to ADR-001's
Azure-first rule. Log Analytics and App Insights are **not** provisioned by default; App
Insights is an optional second exporter on the collector. The ingest licence key is a secret
and lives in Key Vault, read by workload identity.

**Not provisioned**, despite appearing in `idea.md` §17:

| Component | Why |
|-----------|-----|
| Azure AI Search | No consumer until Horizon 3 Track B ([U2](../../../docs/traceability.md#u2--17-provisions-ai-search-which-nothing-uses-until-horizon-3)) |
| Storage | No consumer until documents exist |
| QA / Production environments | Post-Gate-1 |

Do not provision a resource because §17 lists it. Provision it when something uses it
(Principle X).

## Identity — get this right and most security follows

- **User-assigned managed identity** on the container app to reach ACR, Key Vault, and SQL.
- **Managed identity** to SQL and Key Vault. **No connection strings with credentials, no
  access keys, no service principal secrets.**
- Microsoft Entra ID for user authentication.

If you are writing a connection string with a password in it, stop — the design is wrong
(Principle V).

## Terraform conventions

```
infrastructure/terraform/
  modules/<concern>/       reusable
  environments/dev/        composition
```

- Remote state in Azure Storage, **locked**. State can contain secrets — never commit it,
  never commit `*.tfvars`. Already in `.gitignore`.
- The state backend itself is created by a small committed bootstrap script. This is the
  one accepted exception to "no manual setup."
- Terraform provisions Key Vault; it does **not** manage Key Vault contents.
- The container app is itself a Terraform resource (ADR-023); there is no Helm or manifest
  step. The S7 pipeline only updates the image tag.
- Adding QA or production must **reuse** the modules, never copy them.

## Cost — this is real money

The old ADR-007 figure (**$700–1,500/month**) assumed AKS and no longer applies. Compute is
near-free idle; APIM, Front Door, and private endpoints dominate. Re-check with the Azure
pricing calculator.

- Use dev/test SKUs.
- **`terraform destroy` between working sessions.** This is expected practice, not a
  fallback. That it is safe to do is exactly what slice 6's proof establishes.
- Watch for resources that resist clean destruction: soft-deleted Key Vaults, APIM name
  reservations.

## Practical friction to expect in slice 6

Budgeted at 3–4 weeks for good reason:

- **APIM takes 30–45 minutes per apply.** Plan the iteration loop around this.
- Private endpoint plus DNS zone wiring is where most unknown-unknowns live.
- The AzureRM provider lags Azure features; occasionally `azapi` is needed.
- Container Apps environment VNet integration and internal ingress behind APIM need care.

## The research-first bar

`idea.md` §59.2: **a platform is not learned until a rollout has failed and been recovered.**
Slice 6's proof requires deliberately breaking a revision. Standing it up and seeing a
healthy revision teaches you the least useful thing about it.

## Rationalizations that mean you're about to click instead of code

| Thought | Reality |
|---------|---------|
| "I'll just click this one setting to unblock myself, then codify it" | The codify-it-later step almost never happens once the environment works. Now the environment is irreproducible and `terraform destroy`/`apply` silently diverges from reality. |
| "§17 lists this resource, so we should provision it now" | Nothing consumes it yet. Provisioning ahead of a consumer is exactly what Principle X rejects — it's cost and drift risk with no offsetting value. |
| "A connection string is simpler than setting up managed identity" | Simpler now, and it's a credential in config that can leak — the design ADR-013/Principle V exist specifically to close is reopened the moment a password appears in a connection string. |
| "I'll leave the environment up between sessions, tearing down is risky" | Standing the environment up and down safely is exactly what slice 6's proof establishes. Leaving it up is the untested path, not the safe one. |
| "The rollout looks healthy, we don't need to test a failure" | A healthy first revision teaches the least useful thing about Container Apps. The bar is a revision deliberately broken and recovered. |

## Red flags — stop and re-check

- Any resource that exists only because someone clicked it in the portal
- A connection string with a password or access key instead of managed identity
- A resource provisioned with no consumer yet
- Terraform state or `*.tfvars` anywhere near being committed
- An environment left running "just for today" past the working session

**All of these mean: stop, codify it in Terraform (or tear it down), and don't count infrastructure as done until `apply` from empty and `destroy` back to empty both work.**

## Before committing infrastructure

- [ ] `terraform plan` reviewed — no unexpected destroy or replace
- [ ] No secret in variables, state, or outputs
- [ ] Managed identity used, not credentials
- [ ] Private networking where the resource supports it
- [ ] Does anything actually consume this resource yet?
