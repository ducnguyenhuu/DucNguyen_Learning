terraform {
  required_version = ">= 1.9"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  backend "azurerm" {
    # Partial config, same pattern as infrastructure/terraform. The state key is fixed:
    #
    # terraform init \
    #   -backend-config="resource_group_name=rg-dip-tfstate" \
    #   -backend-config="storage_account_name=<from bootstrap-state.sh>" \
    #   -backend-config="container_name=tfstate" \
    #   -backend-config="key=github.tfstate"
  }
}
