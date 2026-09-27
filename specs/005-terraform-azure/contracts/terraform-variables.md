# Terraform Input Variables Contract

**Branch**: `005-terraform-azure` | **Date**: 2026-09-26

## Required Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `environment` | string | Environment name (used in resource naming) | `"dev"` |
| `location` | string | Azure region | `"eastus2"` |
| `resource_group_name` | string | Resource group all environment resources are provisioned into (created by this config, not pre-existing) | `"rg-dip-dev"` |
| `subscription_id` | string | Azure subscription ID | `"xxxxxxxx-xxxx-..."` |
| `tenant_id` | string | Azure AD tenant ID (Entra ID) | `"xxxxxxxx-xxxx-..."` |
| `sql_admin_object_id` | string | Object ID of the Azure AD group/user for SQL admin | `"xxxxxxxx-xxxx-..."` |
| `new_relic_licence_key` | string (sensitive) | New Relic ingest licence key, stored in Key Vault | — |
| `acr_name` | string | Globally unique ACR name (alphanumeric only) | `"acrdipdev"` |

## Optional Variables (with defaults)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `aks_node_vm_size` | string | `"Standard_B2s"` | VM size for AKS node pool |
| `aks_node_count_min` | number | `1` | Minimum node count (autoscaler) |
| `aks_node_count_max` | number | `2` | Maximum node count (autoscaler) |
| `sql_sku` | string | `"Basic"` | Azure SQL database SKU |
| `apim_sku` | string | `"Developer_1"` | APIM SKU name and capacity |
| `frontdoor_sku` | string | `"Standard_AzureFrontDoor"` | Front Door SKU |
| `vnet_address_space` | list(string) | `["10.0.0.0/16"]` | VNet CIDR |
| `otel_sample_rate` | number | `10` | OTel Collector sampling percentage |
| `tags` | map(string) | `{ project = "dip", environment = "dev" }` | Resource tags |

## Two-Phase Apply Overrides (implementation detail, analyze finding F1)

Wiring `apim`'s outbound IP directly into the `networking` module's NSG rule, or `aks`'s OIDC issuer URL directly into the `identity` module, would create real Terraform dependency cycles (`networking` → `apim` → `aks` → `networking`, and similarly for identity/AKS). These two variables break the cycle: left at their defaults on the first `apply`, then set explicitly on a second, deliberate `apply` once the resource they narrow against exists.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `apim_nsg_source_override` | string | `null` | APIM's actual outbound IP (e.g. `"20.1.2.3/32"`), set after APIM is created. `null` uses the broader `ApiManagement` service tag (T010/T032a). |
| `aks_oidc_issuer_url_override` | string | `""` | AKS cluster's OIDC issuer URL, set after AKS is created. Empty until then — the identity module's federated credentials only activate once non-empty. |

## Outputs

| Output | Description |
|--------|-------------|
| `frontdoor_endpoint` | Front Door URL (e.g., `https://dip-dev.azurefd.net`) |
| `apim_gateway_url` | APIM gateway URL |
| `aks_cluster_name` | AKS cluster name (for `az aks get-credentials`) |
| `acr_login_server` | ACR login server (e.g., `acrdipdev.azurecr.io`) |
| `sql_server_fqdn` | Azure SQL Server FQDN |
| `keyvault_uri` | Key Vault URI |
| `aks_oidc_issuer_url` | AKS OIDC issuer URL (for workload identity federation) |

## Bootstrap Variables (one-time state backend)

| Variable | Description |
|----------|-------------|
| `RESOURCE_GROUP` | Resource group for state storage (e.g., `rg-dip-tfstate`) |
| `STORAGE_ACCOUNT` | Storage account name (e.g., `stdiptfstate`) |
| `CONTAINER` | Blob container name (e.g., `tfstate`) |
| `LOCATION` | Azure region for state storage |
