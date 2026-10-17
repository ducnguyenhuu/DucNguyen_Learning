variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "apim_sku" {
  type = string
}

variable "publisher_name" {
  type    = string
  default = "Delivery Intelligence Platform"
}

variable "publisher_email" {
  type    = string
  default = "noreply@example.com"
}

variable "backend_fqdn" {
  description = "Container app's ingress FQDN — APIM backend target."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
