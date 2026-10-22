# Data Model: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

This slice does not introduce application-level entities. The "data model" is the Azure resource topology and its dependency graph — what Terraform provisions and how resources reference each other.

## §1 — Resource Dependency Graph

```text
Resource Group (rg-dip-dev)
├── Storage Account (bootstrap — state backend, outside main Terraform)
│
├── Virtual Network (vnet-dip-dev)
│   ├── Subnet: sn-cae          (Container Apps environment, /23, no delegation)
│   ├── Subnet: sn-sql-pe       (SQL private endpoint)
│   └── Subnet: sn-kv-pe        (Key Vault private endpoint)
│
├── Private DNS Zones
│   ├── privatelink.database.windows.net  → linked to VNet
│   └── privatelink.vaultcore.azure.net   → linked to VNet
│
├── User-Assigned Managed Identities
│   ├── id-tenancy-api    (ACR pull, SQL access, Key Vault read)
│   └── id-otel-collector (Key Vault read — licence key only)
│
├── Key Vault (kv-dip-dev)
│   ├── Private Endpoint → sn-kv-pe
│   ├── RBAC: id-tenancy-api → Key Vault Secrets User
│   ├── RBAC: id-otel-collector → Key Vault Secrets User
│   └── Secrets:
│       └── new-relic-licence-key
│
├── Azure SQL Server (sql-dip-dev)
│   ├── Azure AD-only auth (no SQL auth)
│   ├── Private Endpoint → sn-sql-pe
│   ├── Admin: Azure AD admin from sql_admin_object_id
│   └── Database: sqldb-dip-dev
│
├── Container Registry (acrdipdev)
│   └── RBAC: id-tenancy-api → AcrPull
│
├── Container Apps Environment (cae-dip-dev, Consumption-only, in sn-cae)
│   └── Container App: ca-tenancy-api-dev (single revision mode, 1–3 replicas)
│       ├── Identities: id-tenancy-api, id-otel-collector
│       ├── Ingress: external, port 8080, no source restriction (ADR-024)
│       ├── Secret: new-relic-licence-key (Key Vault reference via id-otel-collector)
│       ├── Container: tenancy-api  (probes on /health/live, /health/ready)
│       └── Container: otel-collector (sidecar; secret mounted at /mnt/secrets)
│
└── Front Door (fd-dip-dev, Standard tier)
    ├── Endpoint: dip-dev.azurefd.net
    ├── Origin Group → container app FQDN
    ├── Route: /* → origin group
    └── Managed TLS certificate
```

## §2 — Identity Relationships

| Managed identity | Used by | Access grants |
|------------------|---------|---------------|
| `id-tenancy-api` | Tenancy API container; registry pull | `AcrPull` on ACR; Azure SQL access via Azure AD; Key Vault Secrets User |
| `id-otel-collector` | Key Vault secret reference for the Collector | Key Vault Secrets User (licence key only) |

Both identities are attached to the one container app. There is no federation: the platform issues tokens to the app directly.

## §3 — Network Flow

```text
Internet
  → Front Door (TLS termination, *.azurefd.net)
    → Container Apps ingress (public)
      → Tenancy API container (port 8080)
        → Azure SQL (via private endpoint, managed identity token)
        → localhost:4317 → OTel Collector sidecar
                             → New Relic OTLP endpoint (outbound HTTPS)
      Key Vault (via private endpoint): the platform resolves the licence-key
        secret reference with id-otel-collector and mounts it as a file
```

## §4 — Terraform Module Dependencies

```text
networking  ←── (VNet, subnets, DNS zones)
identity    ←── (managed identities)
    ↓
keyvault    ←── (needs: networking.sn-kv-pe, identity.id-*)
sql         ←── (needs: networking.sn-sql-pe)
acr         ←── (standalone)
    ↓
containerapp ←── (needs: networking.sn-cae, acr, identity.*, sql, keyvault secret ID)
    ↓
frontdoor   ←── (needs: containerapp FQDN for origin)
```

The one manual ordering is that the container app needs an image: `terraform apply -target=module.acr` first, then `deploy.sh`.
