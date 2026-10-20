output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "cae_subnet_id" {
  value = azurerm_subnet.cae.id
}

output "sql_pe_subnet_id" {
  value = azurerm_subnet.sql_pe.id
}

output "kv_pe_subnet_id" {
  value = azurerm_subnet.kv_pe.id
}


output "sql_private_dns_zone_id" {
  value = azurerm_private_dns_zone.sql.id
}

output "keyvault_private_dns_zone_id" {
  value = azurerm_private_dns_zone.keyvault.id
}
