locals {
  location_prefix = substr(var.region, 0, 3)
  subnet_ranges = cidrsubnets(data.azurerm_virtual_network.res-2.address_space[0], 1, 2, 3, 3)
}
