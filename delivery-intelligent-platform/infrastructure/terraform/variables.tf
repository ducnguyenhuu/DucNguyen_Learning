# Required variables — see contracts/terraform-variables.md for the full contract.

variable "environment" {
  description = "Environment name, used in resource naming."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
}

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "tenant_id" {
  description = "Azure AD (Entra ID) tenant ID."
  type        = string
}

variable "resource_group_name" {
  description = <<-EOT
    Resource group all environment resources are provisioned into. Created by
    this configuration (azurerm_resource_group.main in main.tf) — not
    pre-existing. See analyze finding C1 (specs/005-terraform-azure).
  EOT
  type        = string
}

variable "sql_admin_object_id" {
  description = "Object ID of the Azure AD group/user granted as SQL Server administrator."
  type        = string
}

variable "new_relic_licence_key" {
  description = "New Relic ingest licence key, stored in Key Vault — never in state-adjacent plaintext files."
  type        = string
  sensitive   = true
}

variable "acr_name" {
  description = "Globally unique ACR name (alphanumeric only)."
  type        = string
}

# Optional variables (with defaults) — see contracts/terraform-variables.md.

variable "api_image_tag" {
  description = "Tag of the tenancy-api image already pushed to ACR. Empty until deploy.sh has pushed one; the container app is not created without it."
  type        = string
  default     = ""
}

variable "api_min_replicas" {
  description = "Minimum Tenancy API replicas. 1 is enough: in single revision mode the previous revision keeps serving until the new one is healthy (FR-014)."
  type        = number
  default     = 1
}

variable "api_max_replicas" {
  description = "Maximum Tenancy API replicas."
  type        = number
  default     = 3
}

variable "sql_sku" {
  description = "Azure SQL database SKU."
  type        = string
  default     = "Basic"
}

variable "frontdoor_sku" {
  description = "Front Door SKU."
  type        = string
  default     = "Standard_AzureFrontDoor"
}

variable "vnet_address_space" {
  description = "VNet CIDR."
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "otel_sample_rate" {
  description = "OTel Collector tail-sampling percentage for the default-rate policy."
  type        = number
  default     = 10
}

variable "tags" {
  description = "Resource tags applied to every resource."
  type        = map(string)
  default = {
    project     = "dip"
    environment = "dev"
  }
}

variable "persistent_resource_group_name" {
  description = "Resource group of the pipeline identities created by terraform/persistent. Apply that root first."
  type        = string
  default     = "rg-dip-persistent"
}
