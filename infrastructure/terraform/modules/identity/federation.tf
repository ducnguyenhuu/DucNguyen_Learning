# Workload identity federation (research.md R4): binds each Kubernetes service
# account to its Azure managed identity via the AKS OIDC issuer, so pods authenticate
# with no stored secret. Only created once var.aks_oidc_issuer_url is non-empty — see
# main.tf's two-phase apply note (analyze finding F1's sibling pattern).
resource "azurerm_federated_identity_credential" "tenancy_api" {
  count = var.aks_oidc_issuer_url != "" ? 1 : 0

  name                = "fic-tenancy-api-${var.environment}"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.tenancy_api.id
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:default:tenancy-api"
  audience            = ["api://AzureADTokenExchange"]
}

# T050 extends this file with the otel-collector's federated credential — a second
# block, not a second file (analyze finding F2: same-file conflict avoided by having
# one task create the file and a later task extend it).
resource "azurerm_federated_identity_credential" "otel_collector" {
  count = var.aks_oidc_issuer_url != "" ? 1 : 0

  name                = "fic-otel-collector-${var.environment}"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.otel_collector.id
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:default:otel-collector"
  audience            = ["api://AzureADTokenExchange"]
}
