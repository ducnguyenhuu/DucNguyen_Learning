output "frontdoor_endpoint" {
  description = "Front Door URL, e.g. https://dip-dev.azurefd.net"
  value       = "https://${module.frontdoor.endpoint_hostname}"
}

output "apim_gateway_url" {
  description = "APIM gateway URL."
  value       = module.apim.gateway_url
}

output "aks_cluster_name" {
  description = "AKS cluster name, for `az aks get-credentials`."
  value       = module.aks.cluster_name
}

output "acr_login_server" {
  description = "ACR login server, e.g. acrdipdev.azurecr.io"
  value       = module.acr.login_server
}

output "sql_server_fqdn" {
  description = "Azure SQL Server FQDN."
  value       = module.sql.server_fqdn
}

output "keyvault_uri" {
  description = "Key Vault URI."
  value       = module.keyvault.vault_uri
}

output "aks_oidc_issuer_url" {
  description = "AKS OIDC issuer URL, used for workload identity federation."
  value       = module.aks.oidc_issuer_url
}
