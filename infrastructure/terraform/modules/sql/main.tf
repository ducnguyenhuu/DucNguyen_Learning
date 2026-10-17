# Azure AD-only authentication (research.md R6): no SQL auth login exists at all, so
# there is no SA password to manage, rotate, or leak. The Tenancy API authenticates via
# its managed identity's Azure AD token (Authentication=Active Directory Default in the
# connection string), never a connection-string secret (FR-004, Constitution Principle V).
resource "azurerm_mssql_server" "main" {
  name                = "sql-dip-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  version             = "12.0"

  azuread_administrator {
    login_username              = "sql-admins"
    object_id                   = var.sql_admin_object_id
    azuread_authentication_only = true
  }

  public_network_access_enabled = false

  tags = var.tags
}

resource "azurerm_private_endpoint" "sql" {
  name                = "pe-sql-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.sql_pe_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-sql-${var.environment}"
    private_connection_resource_id = azurerm_mssql_server.main.id
    subresource_names              = ["sqlServer"]
    is_manual_connection            = false
  }

  private_dns_zone_group {
    name                 = "sql-dns-zone-group"
    private_dns_zone_ids = [var.sql_private_dns_zone_id]
  }
}
