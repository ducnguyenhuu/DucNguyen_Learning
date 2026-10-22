# One-time bootstrap: creates the storage account that holds the main configuration's
# remote state. This config's OWN state is local — it must exist before the main
# config's `terraform init -backend-config=...` can point at it (research.md R1).
#
# Run via infrastructure/scripts/bootstrap-state.sh, not directly, so the storage
# account name is generated consistently and printed for use in `terraform init`.

terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "resource_group_name" {
  description = "Resource group for Terraform remote state storage."
  type        = string
  default     = "rg-dip-tfstate"
}

variable "storage_account_name" {
  description = "Globally unique storage account name for Terraform remote state."
  type        = string
}

variable "container_name" {
  description = "Blob container name for Terraform state files."
  type        = string
  default     = "tfstate"
}

variable "location" {
  description = "Azure region for the state storage account."
  type        = string
  default     = "eastus2"
}

resource "azurerm_resource_group" "tfstate" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "tfstate" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"
}

output "resource_group_name" {
  value = azurerm_resource_group.tfstate.name
}

output "storage_account_name" {
  value = azurerm_storage_account.tfstate.name
}

output "container_name" {
  value = azurerm_storage_container.tfstate.name
}
