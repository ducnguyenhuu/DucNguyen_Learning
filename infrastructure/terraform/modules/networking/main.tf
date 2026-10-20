resource "azurerm_virtual_network" "main" {
  name                = "vnet-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  address_space       = var.vnet_address_space
  tags                = var.tags
}

# Container Apps environment subnet. A Consumption-only environment needs at least a /23
# and no subnet delegation (ADR-023). /16 + 7 bits = /23, which does not overlap the /24
# private-endpoint subnets below.
resource "azurerm_subnet" "cae" {
  name                 = "sn-cae"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [cidrsubnet(var.vnet_address_space[0], 7, 0)]
}

resource "azurerm_subnet" "sql_pe" {
  name                 = "sn-sql-pe"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [cidrsubnet(var.vnet_address_space[0], 8, 16)]

  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "kv_pe" {
  name                 = "sn-kv-pe"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [cidrsubnet(var.vnet_address_space[0], 8, 17)]

  private_endpoint_network_policies = "Enabled"
}
