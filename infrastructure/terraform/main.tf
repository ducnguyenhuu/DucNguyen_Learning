terraform {
  backend "azurerm" {
    # Partial config — resource_group_name, storage_account_name, container_name, and
    # key are supplied via `-backend-config` flags at `terraform init` time (FR-002 /
    # Environment key entity: a dedicated .tfvars + fixed state key per environment,
    # not Terraform workspaces — clarified 2026-09-26).
    #
    # terraform init \
    #   -backend-config="resource_group_name=rg-dip-tfstate" \
    #   -backend-config="storage_account_name=<from bootstrap-state.sh>" \
    #   -backend-config="container_name=tfstate" \
    #   -backend-config="key=dev.tfstate"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

provider "azuread" {
  tenant_id = var.tenant_id
}

# The resource group every module below provisions into. Without this, no module can
# plan or apply — see specs/005-terraform-azure's analyze finding C1.
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "networking" {
  source = "./modules/networking"

  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  vnet_address_space  = var.vnet_address_space
  tags                = var.tags
}

module "identity" {
  source = "./modules/identity"

  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

module "keyvault" {
  source = "./modules/keyvault"

  environment                  = var.environment
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  tenant_id                    = var.tenant_id
  kv_pe_subnet_id              = module.networking.kv_pe_subnet_id
  keyvault_private_dns_zone_id = module.networking.keyvault_private_dns_zone_id
  tenancy_api_principal_id     = module.identity.tenancy_api_principal_id
  otel_collector_principal_id  = module.identity.otel_collector_principal_id
  new_relic_licence_key        = var.new_relic_licence_key
  tags                         = var.tags
}

module "sql" {
  source = "./modules/sql"

  environment             = var.environment
  location                = azurerm_resource_group.main.location
  resource_group_name     = azurerm_resource_group.main.name
  sql_admin_object_id     = var.sql_admin_object_id
  sql_sku                 = var.sql_sku
  sql_pe_subnet_id        = module.networking.sql_pe_subnet_id
  sql_private_dns_zone_id = module.networking.sql_private_dns_zone_id
  tags                    = var.tags
}

module "acr" {
  source = "./modules/acr"

  acr_name            = var.acr_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

# The Tenancy API and its OTel Collector sidecar (ADR-023). Needs an image already in ACR,
# so the first-ever apply is two-step: `terraform apply -target=module.acr`, then
# deploy.sh builds and pushes the image and runs the full apply with api_image_tag set.
module "containerapp" {
  source = "./modules/containerapp"

  environment                = var.environment
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  cae_subnet_id              = module.networking.cae_subnet_id
  acr_id                     = module.acr.id
  acr_login_server           = module.acr.login_server
  api_image_tag              = var.api_image_tag
  api_min_replicas           = var.api_min_replicas
  api_max_replicas           = var.api_max_replicas
  tenancy_api_identity_id    = module.identity.tenancy_api_id
  tenancy_api_principal_id   = module.identity.tenancy_api_principal_id
  tenancy_api_client_id      = module.identity.tenancy_api_client_id
  otel_collector_identity_id = module.identity.otel_collector_id
  sql_server_fqdn            = module.sql.server_fqdn
  sql_database_name          = module.sql.database_name
  new_relic_secret_id        = module.keyvault.new_relic_licence_key_secret_id
  otel_sample_rate           = var.otel_sample_rate
  # Only APIM may reach the app's public ingress (FR-007). APIM's IPs exist once the
  # instance does, and the instance does not depend on the app, so no override or
  # second apply is needed; only the APIM *API* below depends on the app's FQDN.
  allowed_ingress_cidrs = [for ip in module.apim.public_ip_addresses : "${ip}/32"]
  tags                  = var.tags
}

module "apim" {
  source = "./modules/apim"

  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  apim_sku            = var.apim_sku
  backend_fqdn        = module.containerapp.app_fqdn
  tags                = var.tags
}

module "frontdoor" {
  source = "./modules/frontdoor"

  environment           = var.environment
  resource_group_name   = azurerm_resource_group.main.name
  frontdoor_sku         = var.frontdoor_sku
  apim_gateway_hostname = replace(module.apim.gateway_url, "https://", "")
  tags                  = var.tags
}
