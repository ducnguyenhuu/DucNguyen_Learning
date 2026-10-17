resource "azurerm_api_management_api" "tenancy_api" {
  name                = "tenancy-api"
  resource_group_name = var.resource_group_name
  api_management_name = azurerm_api_management.main.name
  revision            = "1"
  display_name        = "Tenancy API"
  path                = ""
  protocols           = ["https"]

  service_url = "https://${var.backend_fqdn}"
}

# Simplification for dev: a single GET catch-all operation, not a full multi-verb
# wildcard policy. Sufficient to prove routing/health-check traffic (FR-007's proof
# requirement); a production API definition would import the Tenancy API's OpenAPI
# spec directly instead of hand-rolling operations.
resource "azurerm_api_management_api_operation" "catch_all" {
  operation_id        = "catch-all"
  api_name             = azurerm_api_management_api.tenancy_api.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = var.resource_group_name
  display_name         = "Catch-all passthrough"
  method                = "GET"
  url_template          = "/*"

  response {
    status_code = 200
  }
}
