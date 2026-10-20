variable "environment" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "frontdoor_sku" {
  type = string
}

variable "origin_hostname" {
  description = "Container app ingress FQDN (without scheme), used as the Front Door origin."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
