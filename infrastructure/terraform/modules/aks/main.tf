# The system/initial node pool MUST be the default_node_pool block below, not a
# separate azurerm_kubernetes_cluster_node_pool resource — that resource type is
# reserved by the azurerm provider for *additional* pools only (analyze finding M1).
# Sizing values come from nodepool.tf's locals.
resource "azurerm_kubernetes_cluster" "main" {
  name                = "aks-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  dns_prefix          = "aks-dip-${var.environment}"
  tags                = var.tags

  default_node_pool {
    name                 = "system"
    vm_size              = local.node_vm_size
    vnet_subnet_id       = var.aks_subnet_id
    auto_scaling_enabled = true
    min_count            = local.node_count_min
    max_count            = local.node_count_max

    # research.md R8: spreads FR-014's 2 API replicas across nodes once the
    # autoscaler is at 2, so a single node failure doesn't take down both replicas.
    node_labels = {
      "topology.dip/replica-spread" = "enabled"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  # Workload identity + OIDC issuer (research.md R4) — required for the
  # tenancy-api and otel-collector service accounts to federate to their
  # Azure managed identities with no stored secret.
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay" # research.md R2 — CNI Overlay, not classic Azure CNI
    network_policy       = "calico"
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  # No ingress_application_gateway block — AGIC is not used. Ingress is the
  # community NGINX chart (helm_release.nginx_ingress below), not an AKS addon,
  # since AKS's own "web application routing" addon does not currently expose the
  # NSG/service-tag restriction FR-007 requires as cleanly as a self-managed chart.
}

resource "helm_release" "nginx_ingress" {
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  namespace        = "ingress-nginx"
  create_namespace = true

  depends_on = [azurerm_kubernetes_cluster.main]
}

data "kubernetes_service" "nginx_ingress" {
  metadata {
    name      = "${helm_release.nginx_ingress.name}-controller"
    namespace = helm_release.nginx_ingress.namespace
  }

  depends_on = [helm_release.nginx_ingress]
}
