output "gateway_url" {
  value = azurerm_api_management.main.gateway_url
}

output "public_ip_addresses" {
  description = "APIM instance's outbound public IP addresses — used to narrow the AKS ingress NSG rule (T032a, analyze finding F1)."
  value       = azurerm_api_management.main.public_ip_addresses
}

output "id" {
  value = azurerm_api_management.main.id
}
