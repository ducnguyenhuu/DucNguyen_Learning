---
name: azure-architecture
description: Azure resources, Terraform, AKS, identity, and networking for this platform. Load when touching infrastructure, provisioning resources, or working on deployment.
---

# Azure Architecture

Decisions: [ADR-001](../../../docs/adr/ADR-001-azure-first.md) (Azure),
[ADR-007](../../../docs/adr/ADR-007-aks-in-horizon-1.md) (AKS in Horizon 1),
[ADR-012](../../../docs/adr/ADR-012-terraform.md) (Terraform).

## The absolute rule

**No manual portal configuration.** Anything that exists only because someone clicked it
is a defect — it makes the environment irreproducible and silently breaks the
teardown/rebuild cycle that keeps cost under control.

Slice 6's proof: `terraform apply` into an **empty** subscription produces a working
environment, and `terraform destroy` cleanly removes it.

## Target topology (slice 6)

```
Front Door → API Management → AKS → Azure SQL / Service Bus
                                     Key Vault, Log Analytics, App Insights
                              Managed identity + private endpoints throughout
```

**Not provisioned**, despite appearing in `idea.md` §17:

| Component | Why |
|-----------|-----|
| Azure AI Search | No consumer until Horizon 3 Track B ([U2](../../../docs/traceability.md#u2--17-provisions-ai-search-which-nothing-uses-until-horizon-3)) |
| Storage | No consumer until documents exist |
| QA / Production environments | Post-Gate-1 |

Do not provision a resource because §17 lists it. Provision it when something uses it
(Principle X).

## Identity — get this right and most security follows

- **Workload identity federation** for AKS pods to reach Azure resources.
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
- Terraform provisions the cluster; it does **not** deploy the application. Helm and
  manifests under `deployment/` do that.
- Adding QA or production must **reuse** the modules, never copy them.

## Cost — this is real money

ADR-007's footprint is roughly **$700–1,500/month** at standard SKUs.

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
- Workload identity federation setup is fiddly and poorly documented.

## The research-first bar

`idea.md` §59.2: **AKS is not learned until a rollout has failed and been recovered.**
Slice 6's proof requires deliberately breaking one. Standing the cluster up and seeing
green pods teaches you the least useful thing about it.

## Before committing infrastructure

- [ ] `terraform plan` reviewed — no unexpected destroy or replace
- [ ] No secret in variables, state, or outputs
- [ ] Managed identity used, not credentials
- [ ] Private networking where the resource supports it
- [ ] Does anything actually consume this resource yet?
