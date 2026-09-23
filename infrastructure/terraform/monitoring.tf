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

resource "azurerm_log_analytics_workspace" "application-logs" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}law-${local.location_prefix}-app-logs-01"
  resource_group_name = azurerm_resource_group.monitoring.name
  retention_in_days   = 30
  sku                 = "PerGB2018"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_application_insights" "application-insights" {
  location            = var.region
  name                = "${var.subscription_prefix}${var.environment_prefix}ai-${local.location_prefix}-app-insights-01"
  resource_group_name = azurerm_resource_group.monitoring.name
  workspace_id        = azurerm_log_analytics_workspace.application-logs.id
  application_type    = "other"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_monitor_diagnostic_setting" "function-log-settings" {
  name                       = "${var.subscription_prefix}${var.environment_prefix}ds-${local.location_prefix}-function-log-settings-01"
  target_resource_id         = azurerm_function_app_flex_consumption.consumption-plan.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.application-logs.id

  enabled_log {
    category = "FunctionAppLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "frontdoor-log-settings" {
  name                       = "${var.subscription_prefix}${var.environment_prefix}ds-${local.location_prefix}-frontdoor-log-settings-01"
  target_resource_id         = azurerm_cdn_frontdoor_profile.frontdoor.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.application-logs.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
