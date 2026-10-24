# ADR-022: the app role that lets one named application identity call the Identity API.
#
# The API registration itself is created by infrastructure/scripts/create-entra-app-registrations.sh
# and is not managed here — this file looks it up and manages only the single app role, plus its
# assignment to the load-test identity. That script never touches `appRoles`.

data "azuread_application" "identity_api" {
  display_name = var.api_app_display_name
}

data "azuread_service_principal" "identity_api" {
  client_id = data.azuread_application.identity_api.client_id
}

resource "random_uuid" "automation_role" {}

resource "azuread_application_app_role" "automation_member" {
  application_id = data.azuread_application.identity_api.id
  role_id        = random_uuid.automation_role.result

  allowed_member_types = ["Application"]
  display_name         = "Tenancy automation member"
  description          = "A named application identity that acts as a tenant member (ADR-022)."
  value                = "Tenancy.Automation.Member"
}

# Assigned to the load-test identity only. The deployer must never be able to call the API.
resource "azuread_app_role_assignment" "loadtest" {
  app_role_id         = azuread_application_app_role.automation_member.role_id
  principal_object_id = azurerm_user_assigned_identity.pipeline["loadtest"].principal_id
  resource_object_id  = data.azuread_service_principal.identity_api.object_id
}
