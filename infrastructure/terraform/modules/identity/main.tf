resource "azurerm_user_assigned_identity" "tenancy_api" {
  name                = "id-tenancy-api-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "otel_collector" {
  name                = "id-otel-collector-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}
