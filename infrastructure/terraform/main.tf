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

# kubernetes/helm providers configure themselves from the AKS cluster this same apply
# creates (module.aks below). On a genuinely first apply, Terraform can still build
# this dependency graph correctly (it defers provider-dependent resources until the
# cluster exists) — but if `terraform plan` ever complains about an unknown host
# before the cluster exists, target the aks module first:
#   terraform apply -target=module.aks -var-file=dev.tfvars
# then run the full apply. This is a known Terraform limitation with providers
# configured from resources created in the same configuration, not a bug in this setup.
provider "kubernetes" {
  host                   = module.aks.cluster_id != "" ? data.azurerm_kubernetes_cluster.main.kube_config[0].host : ""
  client_certificate     = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].client_certificate), "")
  client_key             = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].client_key), "")
  cluster_ca_certificate = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].cluster_ca_certificate), "")
}

provider "helm" {
  kubernetes {
    host                   = module.aks.cluster_id != "" ? data.azurerm_kubernetes_cluster.main.kube_config[0].host : ""
    client_certificate     = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].client_certificate), "")
    client_key             = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].client_key), "")
    cluster_ca_certificate = try(base64decode(data.azurerm_kubernetes_cluster.main.kube_config[0].cluster_ca_certificate), "")
  }
}

data "azurerm_kubernetes_cluster" "main" {
  name                = module.aks.cluster_name
  resource_group_name = azurerm_resource_group.main.name

  depends_on = [module.aks]
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

  # T032a's two-phase narrowing (analyze finding F1): wiring this directly to
  # module.apim's output would create a real dependency cycle
  # (networking -> apim -> aks -> networking, since apim needs AKS's ingress
  # IP and AKS needs networking's subnet). Instead, `apim_nsg_source_override`
  # defaults to null (service-tag default applies) and is set explicitly via
  # `-var="apim_nsg_source_override=<ip>/32"` in a second, deliberate apply
  # after T031/T032 create the APIM instance and its outbound IP is known.
  apim_source_address_prefix = coalesce(var.apim_nsg_source_override, "ApiManagement")
}

module "identity" {
  source = "./modules/identity"

  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  # Same two-phase pattern as above: AKS's OIDC issuer URL isn't known until the aks
  # module has been applied once. Left blank ("") for the first apply; the identity
  # module's federated-credential resources (T043/T050) are only created once this is
  # non-empty, so re-running apply after AKS exists is what activates them.
  aks_oidc_issuer_url = var.aks_oidc_issuer_url_override
  tags                = var.tags
}

module "keyvault" {
  source = "./modules/keyvault"

  environment                  = var.environment
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  tenant_id                    = var.tenant_id
  kv_pe_subnet_id               = module.networking.kv_pe_subnet_id
  keyvault_private_dns_zone_id  = module.networking.keyvault_private_dns_zone_id
  tenancy_api_principal_id      = module.identity.tenancy_api_principal_id
  otel_collector_principal_id   = module.identity.otel_collector_principal_id
  new_relic_licence_key         = var.new_relic_licence_key
  tags                          = var.tags
}

module "sql" {
  source = "./modules/sql"

  environment              = var.environment
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  sql_admin_object_id      = var.sql_admin_object_id
  sql_sku                  = var.sql_sku
  sql_pe_subnet_id         = module.networking.sql_pe_subnet_id
  sql_private_dns_zone_id  = module.networking.sql_private_dns_zone_id
  tags                     = var.tags
}

module "acr" {
  source = "./modules/acr"

  acr_name            = var.acr_name
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  tags                 = var.tags
}

module "aks" {
  source = "./modules/aks"

  environment          = var.environment
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  aks_subnet_id        = module.networking.aks_subnet_id
  aks_node_vm_size     = var.aks_node_vm_size
  aks_node_count_min   = var.aks_node_count_min
  aks_node_count_max   = var.aks_node_count_max
  acr_id               = module.acr.id
  tags                 = var.tags
}

module "apim" {
  source = "./modules/apim"

  environment          = var.environment
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  apim_sku             = var.apim_sku
  aks_ingress_fqdn      = module.aks.ingress_public_ip
  tags                 = var.tags
}

module "frontdoor" {
  source = "./modules/frontdoor"

  environment            = var.environment
  resource_group_name    = azurerm_resource_group.main.name
  frontdoor_sku          = var.frontdoor_sku
  apim_gateway_hostname  = replace(module.apim.gateway_url, "https://", "")
  tags                   = var.tags
}
