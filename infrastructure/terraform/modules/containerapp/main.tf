# VNet-integrated, Consumption-only Container Apps environment (ADR-023). External ingress
# because the Developer-tier APIM is not VNet-integrated (research.md R3) — it reaches the
# app over the public endpoint, and the app's ingress IP restriction (app.tf) allows only
# APIM. No logs_destination: ADR-018 makes New Relic the telemetry backend, so no Log
# Analytics workspace is provisioned.
resource "azurerm_container_app_environment" "main" {
  name                           = "cae-dip-${var.environment}"
  resource_group_name            = var.resource_group_name
  location                       = var.location
  infrastructure_subnet_id       = var.cae_subnet_id
  internal_load_balancer_enabled = false
  tags                           = var.tags
}
