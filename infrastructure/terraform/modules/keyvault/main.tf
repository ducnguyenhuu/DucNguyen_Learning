data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "kv-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tenant_id           = var.tenant_id
  sku_name            = "standard"

  # RBAC-only access mode (research.md), not the legacy access-policy model.
  enable_rbac_authorization = true

  public_network_access_enabled = false

  tags = var.tags
}

resource "azurerm_private_endpoint" "keyvault" {
  name                = "pe-kv-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.kv_pe_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-kv-${var.environment}"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection            = false
  }

  private_dns_zone_group {
    name                 = "kv-dns-zone-group"
    private_dns_zone_ids = [var.keyvault_private_dns_zone_id]
  }
}
