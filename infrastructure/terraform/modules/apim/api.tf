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

# Simplification for dev: one catch-all operation per HTTP method rather than importing
# the Tenancy API's OpenAPI spec (a production API definition would). Every method is
# routed because the S7 load test creates tenants with POST.
locals {
  catch_all_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
}

resource "azurerm_api_management_api_operation" "catch_all" {
  for_each = toset(local.catch_all_methods)

  operation_id        = "catch-all-${lower(each.value)}"
  api_name            = azurerm_api_management_api.tenancy_api.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = var.resource_group_name
  display_name        = "Catch-all passthrough (${each.value})"
  method              = each.value
  url_template        = "/*"

  response {
    status_code = 200
  }
}
