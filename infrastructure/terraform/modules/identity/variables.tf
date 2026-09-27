variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "aks_oidc_issuer_url" {
  description = "AKS OIDC issuer URL. Empty string until the AKS module exists (T043/T050 pass the real value once available)."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
