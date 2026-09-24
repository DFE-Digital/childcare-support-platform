resource "azurerm_resource_group" "monitoring" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-monitoring"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_monitor_action_group" "service-support-action" {
  name                = "Service support group"
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

resource "azurerm_monitor_action_group" "budget-alert-action-group" {
  name                = "Budget alert group"
  resource_group_name = azurerm_resource_group.monitoring.name
  short_name          = "BudgetAlert"

  email_receiver {
    name          = "ChildcareSupportPlatform-BudgetAlertEmail"
    email_address = var.support_alert_email
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

import {
  to = azurerm_monitor_diagnostic_setting.application-insights-log-settings
  id = "/subscriptions/${data.azurerm_subscription.current.subscription_id}/resourceGroups/${azurerm_resource_group.monitoring.name}/providers/microsoft.insights/components/${azurerm_application_insights.application-insights.id}/providers/microsoft.insights/diagnosticSettings/s288${var.environment_prefix}ds-uks-app-insights-log-settings-01"
}

resource "azurerm_monitor_diagnostic_setting" "application-insights-log-settings" {
  name                       = "${var.subscription_prefix}${var.environment_prefix}ds-${local.location_prefix}-app-insights-log-settings-01"
  target_resource_id         = azurerm_application_insights.application-insights.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.application-logs.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_metric_alert" "availability-alert" {
  name                = "availability-alert"
  resource_group_name = azurerm_resource_group.monitoring.name
  scopes              = [azurerm_application_insights.application-insights.id]
  description         = "Alert if availability is below configured threshold"
  severity            = 0
  frequency           = "PT1M"
  window_size         = "PT1H"
  enabled             = true
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "availabilityResults/availabilityPercentage"
    aggregation      = "Average"
    operator         = "LessThan"
    // TODO: Figure this out
    threshold = 90
  }

  action {
    action_group_id = azurerm_monitor_action_group.service-support-action.id
  }
}

resource "azurerm_monitor_metric_alert" "function-cpu-usage-alert" {
  name                = "function-cpu-usage-alert"
  resource_group_name = azurerm_resource_group.monitoring.name
  scopes              = [azurerm_function_app_flex_consumption.consumption-plan.id]
  description         = "Alert if CPU usage exceeds the config threshold"
  severity            = 0
  frequency           = "PT1M"
  window_size         = "PT1H"
  enabled             = true
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "CpuPercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    // TODO: Figure this out
    threshold = 90
  }

  action {
    action_group_id = azurerm_monitor_action_group.service-support-action.id
  }
}

// Copied over from the DfE Care Leavers project
// Source: https://github.com/DFE-Digital/care-leavers/blob/main/src/infrastructure/terraform/budget-alerts.tf
// These values below need to be updated to be inline with our projects desired budget :)
locals {
  environment_subscription_budgets = {
    d01 = 100
    t01 = 50
    p01 = 300
  }
}

resource "azurerm_consumption_budget_subscription" "subscription-budget" {
  name            = "${var.subscription_prefix}${var.environment_prefix}cbs-${local.location_prefix}-subscription-budget-01"
  subscription_id = data.azurerm_subscription.current.id
  amount          = local.environment_subscription_budgets[var.environment_prefix]
  time_grain      = "Monthly"

  time_period {
    # Start date must be the first of a month, end date defaults to +10 years when not specified
    start_date = "2026-09-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 80.0
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_groups = [azurerm_monitor_action_group.budget-alert-action-group.id]
  }

  notification {
    enabled        = true
    threshold      = 100.0
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_groups = [azurerm_monitor_action_group.budget-alert-action-group.id]
  }

  notification {
    enabled        = true
    threshold      = 110.0
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_groups = [azurerm_monitor_action_group.budget-alert-action-group.id]
  }
}
