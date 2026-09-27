output "cluster_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "cluster_id" {
  value = azurerm_kubernetes_cluster.main.id
}

output "oidc_issuer_url" {
  value = azurerm_kubernetes_cluster.main.oidc_issuer_url
}

output "kube_config" {
  value     = azurerm_kubernetes_cluster.main.kube_config_raw
  sensitive = true
}

output "ingress_public_ip" {
  description = "Public IP of the NGINX ingress controller's LoadBalancer Service. Requires two applies: the Service (and its Azure-assigned IP) doesn't exist until helm_release.nginx_ingress has reconciled once."
  value       = try(data.kubernetes_service.nginx_ingress.status[0].load_balancer[0].ingress[0].ip, "")
}
