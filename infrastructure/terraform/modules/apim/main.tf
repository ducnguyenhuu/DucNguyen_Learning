# Developer tier, not VNet-integrated (research.md R3, clarified 2026-09-26): Premium
# tier VNet integration would cost ~$2,800/month more than this slice's entire budget.
# APIM reaches the container app's public ingress instead, and the app's ingress IP
# restriction (containerapp module) allows only this instance's public IPs.
resource "azurerm_api_management" "main" {
  name                = "apim-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  publisher_name      = var.publisher_name
  publisher_email     = var.publisher_email
  sku_name            = var.apim_sku
  tags                = var.tags
}
