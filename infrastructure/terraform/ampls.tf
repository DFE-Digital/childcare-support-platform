resource "azurerm_monitor_private_link_scope" "childcare_ampls" {
  name                = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-childcare-ampls"
  resource_group_name = data.azurerm_resource_group.core.name

  ingestion_access_mode = "Open"
  query_access_mode     = "Open"

  tags = {
    Environment = "${var.environment_prefix}"
    Purpose     = "Azure Monitor Private Connectivity"
  }
}

resource "azurerm_monitor_private_link_scoped_service" "childcare_appinsights" {
  name = "${var.subscription_prefix}${var.environment_prefix}-${local.location_prefix}-childcare-appinsights-link"

  resource_group_name = data.azurerm_resource_group.core.name

  scope_name = azurerm_monitor_private_link_scope.childcare_ampls.name

  linked_resource_id = azurerm_application_insights.application-insights.id
}


resource "azurerm_private_endpoint" "childcare_ampls_pe" {
  name                = "pe-childcare-ampls"
  location            = var.region
  resource_group_name = azurerm_resource_group.monitoring.name

  subnet_id = azurerm_subnet.frontend.id

  private_service_connection {
    name                           = "psc-childcare-ampls"
    private_connection_resource_id = azurerm_monitor_private_link_scope.childcare_ampls.id
    subresource_names              = ["azuremonitor"]
    is_manual_connection           = false
  }

  # NEW: Link endpoint to existing private DNS zones
  private_dns_zone_group {
    name = "monitor-dns-group"

    private_dns_zone_ids = [
      for zone in azurerm_private_dns_zone.monitor : zone.id
    ]
  }
}

resource "azurerm_private_dns_zone" "monitor" {
  for_each            = local.monitor_dns_zone_names
  name                = each.value
  resource_group_name = data.azurerm_resource_group.core.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "monitor" {
  for_each = local.monitor_dns_zone_names

  name                  = "childcare-monitor-vnet-link"
  resource_group_name   = data.azurerm_resource_group.core.name
  private_dns_zone_name = azurerm_private_dns_zone.monitor[each.key].name

  virtual_network_id   = data.azurerm_virtual_network.core-vnet.id
  registration_enabled = false

}
