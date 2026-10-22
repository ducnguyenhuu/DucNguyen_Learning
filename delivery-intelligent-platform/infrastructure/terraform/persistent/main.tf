# Identities the CI/CD pipeline uses. They live outside the S6 root because their client
# IDs are copied into GitHub variables once; rebuilding them with the environment would
# break the pipeline after every `terraform destroy`.

resource "azurerm_resource_group" "persistent" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

locals {
  federated_subject = "repo:${var.github_repository}:environment:${var.github_environment}"

  identities = {
    deployer = "id-github-deployer"
    loadtest = "id-loadtest-client"
  }
}

resource "azurerm_user_assigned_identity" "pipeline" {
  for_each = local.identities

  name                = each.value
  resource_group_name = azurerm_resource_group.persistent.name
  location            = azurerm_resource_group.persistent.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github" {
  for_each = local.identities

  name                = "github-${var.github_environment}"
  resource_group_name = azurerm_resource_group.persistent.name
  parent_id           = azurerm_user_assigned_identity.pipeline[each.key].id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = local.federated_subject
  audience            = ["api://AzureADTokenExchange"]
}
