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
  identity_api_principal_id     = module.identity.identity_api_principal_id
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

# The Identity API and its OTel Collector sidecar (ADR-023). Needs an image already in ACR,
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
  identity_api_identity_id    = module.identity.identity_api_id
  identity_api_principal_id   = module.identity.identity_api_principal_id
  identity_api_client_id      = module.identity.identity_api_client_id
  otel_collector_identity_id = module.identity.otel_collector_id
  sql_server_fqdn            = module.sql.server_fqdn
  sql_database_name          = module.sql.database_name
  new_relic_secret_id        = module.keyvault.new_relic_licence_key_secret_id
  otel_sample_rate           = var.otel_sample_rate
  tags                       = var.tags
}

# The CI/CD pipeline's deployer (identity created in terraform/persistent) may push images
# and update this one container app, nothing else: no resource-group, subscription or
# Terraform-state role (S7 research R2). Looked up by name so this root needs no access to
# the other root's state; the persistent root must be applied first.
data "azurerm_user_assigned_identity" "github_deployer" {
  name                = "id-github-deployer"
  resource_group_name = var.persistent_resource_group_name
}

resource "azurerm_role_assignment" "deployer_acr_push" {
  scope                = module.acr.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_user_assigned_identity.github_deployer.principal_id
}

resource "azurerm_role_assignment" "deployer_app_contributor" {
  scope                = module.containerapp.app_id
  role_definition_name = "Container Apps Contributor"
  principal_id         = data.azurerm_user_assigned_identity.github_deployer.principal_id
}

module "frontdoor" {
  source = "./modules/frontdoor"

  environment         = var.environment
  resource_group_name = azurerm_resource_group.main.name
  frontdoor_sku       = var.frontdoor_sku
  origin_hostname     = module.containerapp.app_fqdn
  tags                = var.tags
}
