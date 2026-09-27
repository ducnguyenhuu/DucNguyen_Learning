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

variable "aks_node_vm_size" {
  description = "VM size for the AKS system node pool."
  type        = string
  default     = "Standard_B2s"
}

variable "aks_node_count_min" {
  description = "Minimum node count for the AKS cluster autoscaler."
  type        = number
  default     = 1
}

variable "aks_node_count_max" {
  description = "Maximum node count for the AKS cluster autoscaler."
  type        = number
  default     = 2
}

variable "sql_sku" {
  description = "Azure SQL database SKU."
  type        = string
  default     = "Basic"
}

variable "apim_sku" {
  description = "APIM SKU name and capacity, e.g. Developer_1."
  type        = string
  default     = "Developer_1"
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

# Two-phase apply overrides (analyze finding F1) — both default to "no value yet" and
# are set explicitly on a second `terraform apply` once the resource they narrow
# against actually exists. See main.tf's networking/identity module blocks.

variable "apim_nsg_source_override" {
  description = "APIM instance's actual outbound IP (e.g. \"20.1.2.3/32\"), set after T031/T032 create it. Null uses the broader 'ApiManagement' service tag."
  type        = string
  default     = null
}

variable "aks_oidc_issuer_url_override" {
  description = "AKS cluster's OIDC issuer URL, set after the aks module has been applied once. Empty string until then — identity module's federated credentials only activate once non-empty."
  type        = string
  default     = ""
}
