# VNet-integrated, Consumption-only Container Apps environment (ADR-023). External ingress
# because Front Door Standard reaches its origin over the public endpoint (ADR-024 removed
# API Management). No logs_destination: ADR-018 makes New Relic the telemetry backend, so no Log
# Analytics workspace is provisioned.
resource "azurerm_container_app_environment" "main" {
  name                           = "cae-dip-${var.environment}"
  resource_group_name            = var.resource_group_name
  location                       = var.location
  infrastructure_subnet_id       = var.cae_subnet_id
  internal_load_balancer_enabled = false
  tags                           = var.tags
}
