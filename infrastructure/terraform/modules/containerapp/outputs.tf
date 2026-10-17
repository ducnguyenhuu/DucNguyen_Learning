output "app_name" {
  value = azurerm_container_app.api.name
}

output "app_fqdn" {
  description = "Public FQDN of the app's ingress — the APIM backend."
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "environment_name" {
  value = azurerm_container_app_environment.main.name
}
