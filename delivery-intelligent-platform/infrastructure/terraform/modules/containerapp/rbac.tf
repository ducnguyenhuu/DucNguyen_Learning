# Key Vault access for both identities is granted in the keyvault module. This module owns
# only the registry pull, because the container app cannot start without it.
resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = var.identity_api_principal_id
}
