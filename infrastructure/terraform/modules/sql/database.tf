resource "azurerm_mssql_database" "main" {
  name      = "sqldb-dip-${var.environment}"
  server_id = azurerm_mssql_server.main.id
  sku_name  = var.sql_sku
  tags      = var.tags
}
