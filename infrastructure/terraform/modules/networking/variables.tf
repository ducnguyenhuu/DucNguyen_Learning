variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "vnet_address_space" {
  type = list(string)
}

variable "apim_source_address_prefix" {
  description = <<-EOT
    NSG rule source for AKS ingress inbound (FR-007). Starts as the
    'ApiManagement' regional service tag in Phase 2 (no APIM instance exists
    yet); narrowed to the actual APIM instance's outbound IP once it exists
    (T032a, analyze finding F1).
  EOT
  type    = string
  default = "ApiManagement"
}

variable "tags" {
  type    = map(string)
  default = {}
}
