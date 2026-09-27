# Data Model: Terraform → Azure Infrastructure

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

This slice does not introduce application-level entities. The "data model" is the Azure resource topology and its dependency graph — what Terraform provisions and how resources reference each other.

## §1 — Resource Dependency Graph

```text
Resource Group (rg-dip-dev)
├── Storage Account (bootstrap — state backend, outside main Terraform)
│
├── Virtual Network (vnet-dip-dev)
│   ├── Subnet: sn-aks          (AKS node pool)
│   ├── Subnet: sn-sql-pe       (SQL private endpoint)
│   ├── Subnet: sn-kv-pe        (Key Vault private endpoint)
│   └── Subnet: sn-apim         (APIM, if VNet-integrated)
│
├── Private DNS Zones
│   ├── privatelink.database.windows.net  → linked to VNet
│   └── privatelink.vaultcore.azure.net   → linked to VNet
│
├── User-Assigned Managed Identities
│   ├── id-tenancy-api    (SQL access, Key Vault read)
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
│   ├── Admin: id-tenancy-api (Azure AD admin)
│   └── Database: sqldb-dip-dev
│
├── Container Registry (acrdipdev)
│   └── RBAC: AKS kubelet identity → AcrPull
│
├── AKS Cluster (aks-dip-dev)
│   ├── OIDC Issuer enabled
│   ├── Workload Identity enabled
│   ├── NGINX Ingress Controller (addon)
│   ├── Key Vault CSI Driver (addon)
│   ├── Node Pool: system (Standard_B2s, 1–2 nodes)
│   └── Kubernetes Resources (via Helm):
│       ├── ServiceAccount: tenancy-api (federated → id-tenancy-api)
│       ├── ServiceAccount: otel-collector (federated → id-otel-collector)
│       ├── Deployment: tenancy-api
│       ├── Deployment: otel-collector
│       ├── Service: tenancy-api (ClusterIP)
│       ├── Service: otel-collector (ClusterIP, ports 4317/4318)
│       ├── Ingress: tenancy-api (NGINX)
│       ├── ConfigMap: otel-collector-config
│       └── SecretProviderClass: kv-secrets (CSI driver)
│
├── API Management (apim-dip-dev, Developer tier)
│   ├── API: tenancy-api (backend → AKS ingress)
│   └── Policy: rate-limit, cors, jwt-validation (optional)
│
└── Front Door (fd-dip-dev, Standard tier)
    ├── Endpoint: dip-dev.azurefd.net
    ├── Origin Group → APIM gateway URL
    ├── Route: /* → origin group
    └── Managed TLS certificate
```

## §2 — Identity Relationships

| Kubernetes Service Account | Azure Managed Identity | Access Grants |
|---------------------------|----------------------|---------------|
| `tenancy-api` | `id-tenancy-api` | Azure SQL DB admin (Azure AD); Key Vault Secrets User |
| `otel-collector` | `id-otel-collector` | Key Vault Secrets User (licence key only) |

Workload Identity Federation binds each Kubernetes service account to its Azure identity via the AKS cluster's OIDC issuer URL + the service account's namespace and name as the subject.

## §3 — Network Flow

```text
Internet
  → Front Door (TLS termination, *.azurefd.net)
    → APIM (API policies, Developer tier)
      → AKS Ingress Controller (NGINX, in-cluster)
        → Tenancy API pod (port 8080)
          → Azure SQL (via private endpoint, managed identity token)
          → Key Vault (via private endpoint, workload identity token)
        → OTel Collector pod (ports 4317/4318)
          → New Relic OTLP endpoint (outbound HTTPS)
```

## §4 — Terraform Module Dependencies

```text
networking  ←── (VNet, subnets, DNS zones)
    ↓
identity    ←── (managed identities — need no VNet, but other modules need them)
    ↓
keyvault    ←── (needs: networking.sn-kv-pe, identity.id-*)
sql         ←── (needs: networking.sn-sql-pe, identity.id-tenancy-api)
acr         ←── (standalone, but AKS needs its ID)
    ↓
aks         ←── (needs: networking.sn-aks, acr.id, identity.*)
    ↓
apim        ←── (needs: aks ingress IP/FQDN for backend)
    ↓
frontdoor   ←── (needs: apim gateway URL for origin)
```

This ordering drives the Terraform dependency graph. Modules lower in the chain implicitly depend on modules above via output references.
