resource "azurerm_role_assignment" "identity_api_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.identity_api_principal_id
}

resource "azurerm_role_assignment" "otel_collector_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.otel_collector_principal_id
}
