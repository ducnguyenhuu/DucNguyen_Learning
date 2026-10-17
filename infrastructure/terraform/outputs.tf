output "frontdoor_endpoint" {
  description = "Front Door URL, e.g. https://dip-dev.azurefd.net"
  value       = "https://${module.frontdoor.endpoint_hostname}"
}

output "apim_gateway_url" {
  description = "APIM gateway URL."
  value       = module.apim.gateway_url
}

output "container_app_name" {
  description = "Container app name, for `az containerapp` commands."
  value       = module.containerapp.app_name
}

output "acr_login_server" {
  description = "ACR login server, e.g. acrdipdev.azurecr.io"
  value       = module.acr.login_server
}

output "sql_server_fqdn" {
  description = "Azure SQL Server FQDN."
  value       = module.sql.server_fqdn
}

output "keyvault_uri" {
  description = "Key Vault URI."
  value       = module.keyvault.vault_uri
}

output "resource_group_name" {
  description = "Resource group holding the environment, for `az containerapp` commands."
  value       = azurerm_resource_group.main.name
}
