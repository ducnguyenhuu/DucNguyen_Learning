variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "cae_subnet_id" {
  description = "Subnet for the Container Apps environment (Consumption-only, /23 minimum)."
  type        = string
}

variable "acr_id" {
  description = "ACR resource ID, for the AcrPull role assignment."
  type        = string
}

variable "acr_login_server" {
  type = string
}

variable "api_image_tag" {
  description = "Tag of the tenancy-api image already pushed to ACR. The container app cannot be created without a real image, so this must be set (deploy.sh does) on the first full apply."
  type        = string
  default     = ""
}

variable "api_min_replicas" {
  description = "FR-014: at least 2 replicas, so a failed new revision never leaves the app without a serving replica."
  type        = number
  default     = 2
}

variable "api_max_replicas" {
  type    = number
  default = 3
}

variable "tenancy_api_identity_id" {
  description = "User-assigned identity: ACR pull and Azure SQL access."
  type        = string
}

variable "tenancy_api_principal_id" {
  type = string
}

variable "tenancy_api_client_id" {
  description = "Passed as AZURE_CLIENT_ID so DefaultAzureCredential selects this user-assigned identity."
  type        = string
}

variable "otel_collector_identity_id" {
  description = "User-assigned identity used to read the New Relic licence key from Key Vault."
  type        = string
}

variable "sql_server_fqdn" {
  type = string
}

variable "sql_database_name" {
  type = string
}

variable "new_relic_secret_id" {
  description = "Versionless Key Vault secret ID of the New Relic ingest licence key."
  type        = string
}

variable "otel_sample_rate" {
  type = number
}

variable "allowed_ingress_cidrs" {
  description = "Only these CIDRs may reach the app's ingress (FR-007) — the APIM outbound IPs."
  type        = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
