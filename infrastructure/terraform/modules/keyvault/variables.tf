variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "kv_pe_subnet_id" {
  type = string
}

variable "keyvault_private_dns_zone_id" {
  type = string
}

variable "tenancy_api_principal_id" {
  type = string
}

variable "otel_collector_principal_id" {
  type = string
}

variable "new_relic_licence_key" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
