resource "azurerm_cdn_frontdoor_profile" "main" {
  name                = "fd-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  sku_name            = var.frontdoor_sku
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  name                     = "dip-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  tags                     = var.tags
}
