variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "tenant_id" {
  description = "Entra ID tenant ID."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "australiaeast"
}

variable "resource_group_name" {
  description = "Resource group for the pipeline identities. Separate from the S6 environment's group so `terraform destroy` there leaves these standing."
  type        = string
  default     = "rg-dip-persistent"
}

variable "github_repository" {
  description = "GitHub repository slug (owner/name) allowed to use the federated credentials."
  type        = string
  default     = "ducnguyenhuu/delivery-intelligent-platform"
}

variable "github_environment" {
  description = "GitHub environment whose jobs may assume the identities."
  type        = string
  default     = "dev"
}

variable "api_app_display_name" {
  description = "Display name of the Identity API app registration created by infrastructure/scripts/create-entra-app-registrations.sh."
  type        = string
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
