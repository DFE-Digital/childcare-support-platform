data "azurerm_resource_group" "core" {
  name = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-core"
}

data "azurerm_network_security_group" "core-nsg" {
  name                = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-nsg-01"
  resource_group_name = data.azurerm_resource_group.core.name
}

data "azurerm_virtual_network" "core-vnet" {
  name                = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  resource_group_name = data.azurerm_resource_group.core.name
}

moved {
  from = module.core.azurerm_subnet.res-3
  to   = azurerm_subnet.backend
}

resource "azurerm_subnet" "backend" {
  address_prefixes                              = [local.subnet_ranges[2]]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-backend"
  network_security_group_id_wo                  = data.azurerm_network_security_group.core-nsg.id
  network_security_group_id_wo_version          = 1
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.core.name
  service_endpoint_policy_ids                   = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  delegation {
    name = "Microsoft.Web.serverFarms"
    service_delegation {
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
      name    = "Microsoft.Web/serverFarms"
    }
  }
  depends_on = [
    data.azurerm_virtual_network.core-vnet,
  ]
}

moved {
  from = module.core.azurerm_subnet.res-5
  to   = azurerm_subnet.container-apps
}

resource "azurerm_subnet" "container-apps" {
  address_prefixes                              = [local.subnet_ranges[0]]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-containerApps"
  network_security_group_id_wo                  = data.azurerm_network_security_group.core-nsg.id
  network_security_group_id_wo_version          = 1
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.core.name
  service_endpoint_policy_ids                   = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.core-vnet,
  ]
}

moved {
  from = module.core.azurerm_subnet.res-7
  to   = azurerm_subnet.frontend
}

resource "azurerm_subnet" "frontend" {
  address_prefixes                              = [local.subnet_ranges[1]]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-frontend"
  network_security_group_id_wo                  = data.azurerm_network_security_group.core-nsg.id
  network_security_group_id_wo_version          = 1
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.core.name
  service_endpoint_policy_ids                   = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.core-vnet,
  ]
}

moved {
  from = module.core.azurerm_subnet.res-9
  to   = azurerm_subnet.actions-runner
}

resource "azurerm_subnet" "actions-runner" {
  address_prefixes                              = [local.subnet_ranges[3]]
  default_outbound_access_enabled               = false
  name                                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-snet-githubActionsRunner"
  network_security_group_id_wo                  = data.azurerm_network_security_group.core-nsg.id
  network_security_group_id_wo_version          = 1
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
  resource_group_name                           = data.azurerm_resource_group.core.name
  service_endpoint_policy_ids                   = []
  virtual_network_name                          = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.core-vnet,
  ]
}

resource "azurerm_virtual_network_peering" "hub-peering" {
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
  resource_group_name                    = data.azurerm_resource_group.core.name
  use_remote_gateways                    = true
  virtual_network_name                   = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-core-vn-01"
  depends_on = [
    data.azurerm_virtual_network.core-vnet,
  ]
}
