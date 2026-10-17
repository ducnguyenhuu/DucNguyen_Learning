output "resource_group_name" {
  value = azurerm_resource_group.persistent.name
}

output "deployer_client_id" {
  description = "Becomes the AZURE_DEPLOYER_CLIENT_ID repository variable."
  value       = azurerm_user_assigned_identity.pipeline["deployer"].client_id
}

output "deployer_principal_id" {
  value = azurerm_user_assigned_identity.pipeline["deployer"].principal_id
}

output "loadtest_client_id" {
  description = "Becomes the AZURE_LOADTEST_CLIENT_ID repository variable."
  value       = azurerm_user_assigned_identity.pipeline["loadtest"].client_id
}

output "loadtest_principal_id" {
  value = azurerm_user_assigned_identity.pipeline["loadtest"].principal_id
}
