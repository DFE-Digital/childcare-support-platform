locals {
  location_prefix = substr(var.region, 0, 3)
  subnet_ranges   = cidrsubnets(data.azurerm_virtual_network.core-vnet.address_space[0], 1, 2, 3, 3)
  monitor_dns_zone_names = toset([
    "privatelink.monitor.azure.com",
    "privatelink.oms.opinsights.azure.com",
    "privatelink.ods.opinsights.azure.com",
    "privatelink.agentsvc.azure-automation.net"
  ])
}
