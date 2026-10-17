variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "sql_admin_object_id" {
  type = string
}

variable "sql_sku" {
  type = string
}

variable "sql_pe_subnet_id" {
  type = string
}

variable "sql_private_dns_zone_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
