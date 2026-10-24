output "identity_api_id" {
  value = azurerm_user_assigned_identity.identity_api.id
}

output "identity_api_principal_id" {
  value = azurerm_user_assigned_identity.identity_api.principal_id
}

output "identity_api_client_id" {
  value = azurerm_user_assigned_identity.identity_api.client_id
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
