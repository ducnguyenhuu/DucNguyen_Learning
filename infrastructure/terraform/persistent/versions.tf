terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "azurerm" {
    # Partial config. Own state key so these identities survive `terraform destroy` of the
    # S6 environment:
    #
    # terraform init \
    #   -backend-config="resource_group_name=rg-dip-tfstate" \
    #   -backend-config="storage_account_name=<from bootstrap-state.sh>" \
    #   -backend-config="container_name=tfstate" \
    #   -backend-config="key=persistent.tfstate"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

provider "azuread" {
  tenant_id = var.tenant_id
}
