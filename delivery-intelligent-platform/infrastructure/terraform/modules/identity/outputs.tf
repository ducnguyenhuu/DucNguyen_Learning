output "tenancy_api_id" {
  value = azurerm_user_assigned_identity.tenancy_api.id
}

output "tenancy_api_principal_id" {
  value = azurerm_user_assigned_identity.tenancy_api.principal_id
}

output "tenancy_api_client_id" {
  value = azurerm_user_assigned_identity.tenancy_api.client_id
}

output "otel_collector_id" {
  value = azurerm_user_assigned_identity.otel_collector.id
}

output "otel_collector_principal_id" {
  value = azurerm_user_assigned_identity.otel_collector.principal_id
}

output "otel_collector_client_id" {
  value = azurerm_user_assigned_identity.otel_collector.client_id
}
