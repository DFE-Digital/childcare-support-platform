resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-core"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = "Childcare Platform"
  }
}

resource "azurerm_network_security_group" "res-1" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-nsg-01"
  resource_group_name = azurerm_resource_group.res-0.name
  security_rule       = []
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = "Childcare Platform"
  }
}

resource "azurerm_virtual_network" "res-2" {
  address_space                  = ["10.226.188.0/25"]
  dns_servers                    = ["10.210.64.4", "10.210.64.5"]
  location                       = var.region
  name                           = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  private_endpoint_vnet_policies = "Disabled"
  resource_group_name            = azurerm_resource_group.res-0.name
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = "Childcare Platform"
  }
}

resource "azurerm_subnet" "res-3" {
  address_prefixes                              = ["10.226.188.96/28"]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-backend"
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  delegation {
    name = "Microsoft.Web.serverFarms"
    service_delegation {
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
      name    = "Microsoft.Web/serverFarms"
    }
  }
  depends_on = [
    azurerm_virtual_network.res-2,
  ]
}

resource "azurerm_subnet_network_security_group_association" "res-4" {
  network_security_group_id = azurerm_network_security_group.res-1.id
  subnet_id                 = azurerm_subnet.res-3.id
}

resource "azurerm_subnet" "res-5" {
  address_prefixes                              = ["10.226.188.0/26"]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-containerApps"
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    azurerm_virtual_network.res-2,
  ]
}

resource "azurerm_subnet_network_security_group_association" "res-6" {
  network_security_group_id = azurerm_network_security_group.res-1.id
  subnet_id                 = azurerm_subnet.res-5.id
}

resource "azurerm_subnet" "res-7" {
  address_prefixes                              = ["10.226.188.64/27"]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-frontend"
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    azurerm_virtual_network.res-2,
  ]
}

resource "azurerm_subnet_network_security_group_association" "res-8" {
  network_security_group_id = azurerm_network_security_group.res-1.id
  subnet_id                 = azurerm_subnet.res-7.id
}

resource "azurerm_subnet" "res-9" {
  address_prefixes                              = ["10.226.188.112/28"]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-githubActionsRunner"
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  delegation {
    name = "GitHub.Network/networkSettings"
    service_delegation {
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
      name    = "GitHub.Network/networkSettings"
    }
  }
  depends_on = [
    azurerm_virtual_network.res-2,
  ]
}

resource "azurerm_subnet_network_security_group_association" "res-10" {
  network_security_group_id = azurerm_network_security_group.res-1.id
  subnet_id                 = azurerm_subnet.res-9.id
}

resource "azurerm_virtual_network_peering" "res-11" {
  count                                  = var.remote_virtual_network_id != null ? 1 : 0
  allow_forwarded_traffic                = false
  allow_gateway_transit                  = false
  allow_virtual_network_access           = true
  local_subnet_names                     = []
  name                                   = "RemoteVnetToHubPeering_148e6504-86b9-4335-b16e-4cfd42cab5ca"
  only_ipv6_peering_enabled              = false
  peer_complete_virtual_networks_enabled = true
  remote_subnet_names                    = []
  remote_virtual_network_id              = var.remote_virtual_network_id
  resource_group_name                    = azurerm_resource_group.res-0.name
  use_remote_gateways                    = true
  virtual_network_name                   = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    azurerm_virtual_network.res-2,
  ]
}
