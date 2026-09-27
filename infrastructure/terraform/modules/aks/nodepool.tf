# Sizing for the default_node_pool block in main.tf — this file holds configuration
# only; it does not declare a second node-pool resource (analyze finding M1).
locals {
  node_vm_size   = var.aks_node_vm_size
  node_count_min = var.aks_node_count_min
  node_count_max = var.aks_node_count_max
}
