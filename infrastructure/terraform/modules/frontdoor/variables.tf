variable "environment" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "frontdoor_sku" {
  type = string
}

variable "apim_gateway_hostname" {
  description = "APIM gateway hostname (without scheme), used as the Front Door origin."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
