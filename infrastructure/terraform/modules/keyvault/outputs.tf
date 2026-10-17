output "vault_id" {
  value = azurerm_key_vault.main.id
}

output "vault_name" {
  value = azurerm_key_vault.main.name
}

output "vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "new_relic_licence_key_secret_id" {
  description = "Versionless secret ID, so the container app always reads the current version."
  value       = azurerm_key_vault_secret.new_relic_licence_key.versionless_id
}
