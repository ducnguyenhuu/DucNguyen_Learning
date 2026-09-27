# Developer tier, not VNet-integrated (research.md R3, clarified 2026-09-26): Premium
# tier VNet integration would cost ~$2,800/month more than this slice's entire budget.
# APIM reaches AKS's ingress controller over its public IP instead, with the NSG rule
# in the networking module (T010/T032a) restricting who can reach that IP.
resource "azurerm_api_management" "main" {
  name                = "apim-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  publisher_name      = var.publisher_name
  publisher_email     = var.publisher_email
  sku_name            = var.apim_sku
  tags                = var.tags
}
