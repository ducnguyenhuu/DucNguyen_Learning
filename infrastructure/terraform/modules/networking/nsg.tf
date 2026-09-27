# FR-007 (clarified 2026-09-26): AKS ingress uses a public IP (APIM Developer tier is
# not VNet-integrated — research.md R3), restricted via NSG rather than left open.
#
# Two-step tightening (analyze finding F1): this NSG is created in the Foundational
# phase, before any APIM instance exists, so it starts with the broad `ApiManagement`
# regional service tag — the only thing available pre-instance. Once the apim module
# creates a real instance (T031/T032), T032a narrows `var.apim_source_address_prefix`
# from the service tag to that instance's actual outbound IP by re-applying this module
# with a different input — the rule itself doesn't move, only its source narrows.
resource "azurerm_network_security_group" "aks_ingress" {
  name                = "nsg-aks-ingress-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  security_rule {
    name                       = "AllowApimInbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = var.apim_source_address_prefix
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllOtherInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}
