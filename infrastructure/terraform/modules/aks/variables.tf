variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "aks_subnet_id" {
  type = string
}

variable "aks_node_vm_size" {
  type = string
}

variable "aks_node_count_min" {
  type = number
}

variable "aks_node_count_max" {
  type = number
}

variable "acr_id" {
  description = "ACR resource ID, for the AcrPull role assignment in rbac.tf."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
