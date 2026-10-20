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
| `api_image_tag` | string | `""` | Image tag in ACR. Empty fails the container app's plan; `deploy.sh` supplies it |
| `api_min_replicas` | number | `1` | Minimum API replicas (FR-014) |
| `api_max_replicas` | number | `3` | Maximum API replicas |
| `sql_sku` | string | `"Basic"` | Azure SQL database SKU |
| `frontdoor_sku` | string | `"Standard_AzureFrontDoor"` | Front Door SKU |
| `vnet_address_space` | list(string) | `["10.0.0.0/16"]` | VNet CIDR |
| `otel_sample_rate` | number | `10` | OTel Collector sampling percentage |
| `tags` | map(string) | `{ project = "dip", environment = "dev" }` | Resource tags |

## First-apply ordering

There are no override variables. Front Door takes the container app's FQDN as its origin, so the graph has no cycle (ADR-023 removed the AKS OIDC and NSG cycles). The one ordering constraint is that the app needs an image: run `terraform apply -target=module.acr`, then `deploy.sh`.

## Outputs

| Output | Description |
|--------|-------------|
| `frontdoor_endpoint` | Front Door URL (e.g., `https://dip-dev.azurefd.net`) |
| `container_app_name` | Container app name (for `az containerapp` commands) |
| `resource_group_name` | Resource group holding the environment |
| `acr_login_server` | ACR login server (e.g., `acrdipdev.azurecr.io`) |
| `sql_server_fqdn` | Azure SQL Server FQDN |
| `keyvault_uri` | Key Vault URI |

## Bootstrap Variables (one-time state backend)

| Variable | Description |
|----------|-------------|
| `RESOURCE_GROUP` | Resource group for state storage (e.g., `rg-dip-tfstate`) |
| `STORAGE_ACCOUNT` | Storage account name (e.g., `stdiptfstate`) |
| `CONTAINER` | Blob container name (e.g., `tfstate`) |
| `LOCATION` | Azure region for state storage |
