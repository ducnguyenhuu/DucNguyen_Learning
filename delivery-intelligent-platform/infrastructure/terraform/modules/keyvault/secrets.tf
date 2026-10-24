# The New Relic ingest licence key — value comes from the sensitive
# new_relic_licence_key variable, never hardcoded. Depends on the RBAC grant so the
# apply-time identity (human or CI) already has write access is irrelevant here; what
# matters is that role_assignment exists before anything tries to *read* this secret.
resource "azurerm_key_vault_secret" "new_relic_licence_key" {
  name         = "new-relic-licence-key"
  value        = var.new_relic_licence_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [
    azurerm_role_assignment.identity_api_secrets_user,
    azurerm_role_assignment.otel_collector_secrets_user,
  ]
}
