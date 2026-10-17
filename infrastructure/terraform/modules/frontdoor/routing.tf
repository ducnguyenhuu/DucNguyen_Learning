resource "azurerm_cdn_frontdoor_origin_group" "apim" {
  name                     = "og-apim-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id

  load_balancing {}

  health_probe {
    path                = "/health/live"
    request_type        = "GET"
    protocol            = "Https"
    interval_in_seconds = 30
  }
}

resource "azurerm_cdn_frontdoor_origin" "apim" {
  name                          = "origin-apim-${var.environment}"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.apim.id

  enabled                        = true
  host_name                      = var.apim_gateway_hostname
  origin_host_header             = var.apim_gateway_hostname
  https_port                     = 443
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_route" "main" {
  name                          = "route-main-${var.environment}"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.apim.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.apim.id]

  supported_protocols    = ["Http", "Https"]
  patterns_to_match      = ["/*"]
  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true # FR-007: TLS termination at Front Door
  link_to_default_domain = true # Uses the *.azurefd.net managed domain/certificate
}
