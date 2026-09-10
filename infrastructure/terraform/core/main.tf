data "azurerm_subscription" "current" {}

data "azurerm_resource_group" "res-0" {
  name = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-core"
}

data "azurerm_network_security_group" "res-1" {
  name = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-nsg-01"
  resource_group_name = data.azurerm_resource_group.res-0.name
}

data "azurerm_virtual_network" "res-2" {
  name = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  resource_group_name = data.azurerm_resource_group.res-0.name
}

// starting address range
// azurerm_virtual_network.res-2.address_space
// 10.226.188.0/25

// cidrsubnet
// cidrsubnets
// -> cidrsubnets(azurerm_virtual_network.res-2.address_space, 1, 2, 3, 3)
// > ["starting.../26". "starting.../27", starting.../28, starting.../28]
// subnet_spaces

// subnet_spaces[0]
// subnet_spaces[1]
// subnet_spaces[2]
// subnet_spaces[3]

resource "azurerm_subnet" "res-3" {
  address_prefixes                              = [local.subnet_ranges[2]]
    # "10.226.188.96/28"
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-backend"
  network_security_group_id_wo                  = data.azurerm_network_security_group.res-1.id
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.res-0.name
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
    data.azurerm_virtual_network.res-2,
  ]
}

# resource "azurerm_subnet_network_security_group_association" "res-4" {
#   network_security_group_id = data.azurerm_network_security_group.res-1.id
#   subnet_id                 = azurerm_subnet.res-3.id
# }

resource "azurerm_subnet" "res-5" {
  address_prefixes                              = [local.subnet_ranges[0]]
    # "10.226.188.0/26"
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-containerApps"
  network_security_group_id_wo                  = data.azurerm_network_security_group.res-1.id
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.res-2,
  ]
}

# resource "azurerm_subnet_network_security_group_association" "res-6" {
#   network_security_group_id = data.azurerm_network_security_group.res-1.id
#   subnet_id                 = azurerm_subnet.res-5.id
# }

resource "azurerm_subnet" "res-7" {
  address_prefixes                              = [local.subnet_ranges[1]]
    # "10.226.188.64/27"
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-frontend"
  network_security_group_id_wo                  = data.azurerm_network_security_group.res-1.id
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.res-0.name
  service_endpoint_policy_ids                   = []
  service_endpoints                             = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.res-2,
  ]
}

# resource "azurerm_subnet_network_security_group_association" "res-8" {
#   network_security_group_id = data.azurerm_network_security_group.res-1.id
#   subnet_id                 = azurerm_subnet.res-7.id
# }

resource "azurerm_subnet" "res-9" {
  address_prefixes                              = [local.subnet_ranges[3]]
    # "10.226.188.112/28"
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-githubActionsRunner"
  network_security_group_id_wo                  = data.azurerm_network_security_group.res-1.id
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.res-0.name
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
    data.azurerm_virtual_network.res-2,
  ]
}

# resource "azurerm_subnet_network_security_group_association" "res-10" {
#   network_security_group_id = data.azurerm_network_security_group.res-1.id
#   subnet_id                 = azurerm_subnet.res-9.id
# }

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
  resource_group_name                    = data.azurerm_resource_group.res-0.name
  use_remote_gateways                    = true
  virtual_network_name                   = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.res-2,
  ]
}
