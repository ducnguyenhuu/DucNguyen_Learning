output "gateway_url" {
  value = azurerm_api_management.main.gateway_url
}

output "public_ip_addresses" {
  description = "APIM instance's public IP addresses — the only sources the container app's ingress accepts (FR-007)."
  value       = azurerm_api_management.main.public_ip_addresses
}

output "id" {
  value = azurerm_api_management.main.id
}
