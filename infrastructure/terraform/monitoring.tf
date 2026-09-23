resource "azurerm_resource_group" "monitoring" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-monitoring"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_monitor_action_group" "service-support-action" {
  name                = "Service Support"
  resource_group_name = azurerm_resource_group.monitoring.name
  short_name          = "Support"

  email_receiver {
    name                    = "send-to-support"
    email_address           = var.support_alert_email
    use_common_alert_schema = true
  }
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}
