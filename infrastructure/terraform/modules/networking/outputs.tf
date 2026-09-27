output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "aks_subnet_id" {
  value = azurerm_subnet.aks.id
}

output "sql_pe_subnet_id" {
  value = azurerm_subnet.sql_pe.id
}

output "kv_pe_subnet_id" {
  value = azurerm_subnet.kv_pe.id
}

output "apim_subnet_id" {
  value = azurerm_subnet.apim.id
}

output "sql_private_dns_zone_id" {
  value = azurerm_private_dns_zone.sql.id
}

output "keyvault_private_dns_zone_id" {
  value = azurerm_private_dns_zone.keyvault.id
}

output "aks_ingress_nsg_id" {
  value = azurerm_network_security_group.aks_ingress.id
}
