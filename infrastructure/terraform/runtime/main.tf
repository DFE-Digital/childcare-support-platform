resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-runtime"
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}

resource "azurerm_storage_account" "res-2" {
  access_tier                       = "Hot"
  account_kind                      = "StorageV2"
  account_replication_type          = "LRS"
  account_tier                      = "Standard"
  allow_nested_items_to_be_public   = false
  cross_tenant_replication_enabled  = false
  default_to_oauth_authentication   = true
  dns_endpoint_type                 = "Standard"
  https_traffic_only_enabled        = true
  infrastructure_encryption_enabled = false
  is_hns_enabled                    = false
  large_file_share_enabled          = false
  local_user_enabled                = true
  location                          = var.region
  min_tls_version                   = "TLS1_2"
  name                              = "${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${var.unique_suffix}"
  nfsv3_enabled                     = false
  public_network_access_enabled     = true
  queue_encryption_key_type         = "Service"
  resource_group_name               = azurerm_resource_group.res-0.name
  sftp_enabled                      = false
  shared_access_key_enabled         = true
  table_encryption_key_type         = "Service"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  blob_properties {
    change_feed_enabled      = false
    last_access_time_enabled = false
    versioning_enabled       = false
  }
  network_rules {
    bypass                     = ["None"]
    default_action             = "Allow"
    ip_rules                   = []
    virtual_network_subnet_ids = []
  }
  share_properties {
    retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "res-4" {
  container_access_type = "private"
  metadata              = {}
  name                  = "azure-webjobs-hosts"
  storage_account_id    = azurerm_storage_account.res-2.id
}

resource "azurerm_storage_container" "res-5" {
  container_access_type = "private"
  metadata              = {}
  name                  = "azure-webjobs-secrets"
  storage_account_id    = azurerm_storage_account.res-2.id
}

resource "azurerm_storage_container" "res-6" {
  container_access_type = "private"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${var.unique_suffix}"
  storage_account_id    = azurerm_storage_account.res-2.id
}

resource "azurerm_service_plan" "res-10" {
  location                        = var.region
  maximum_elastic_worker_count    = 1
  name                            = "ASP-${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime-${var.unique_suffix}"
  os_type                         = "Linux"
  per_site_scaling_enabled        = false
  premium_plan_auto_scale_enabled = false
  resource_group_name             = azurerm_resource_group.res-0.name
  sku_name                        = "FC1"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  zone_balancing_enabled = false
}

resource "azurerm_function_app_flex_consumption" "res-11" {
  app_settings                       = {}
  client_certificate_enabled         = false
  client_certificate_exclusion_paths = ""
  client_certificate_mode            = "Required"
  enabled                            = true
  https_only                         = true
  instance_memory_in_mb              = 512
  location                           = var.region
  maximum_instance_count             = 100
  name                               = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  public_network_access_enabled      = true
  resource_group_name                = azurerm_resource_group.res-0.name
  runtime_name                       = "custom"
  runtime_version                    = "1.0"
  service_plan_id                    = azurerm_service_plan.res-10.id
  storage_authentication_type        = "StorageAccountConnectionString"
  storage_container_endpoint         = "https://${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${var.unique_suffix}.blob.core.windows.net/${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${var.unique_suffix}"
  storage_container_type             = "blobContainer"
  tags = {
    Environment                              = "Dev"
    Product                                  = "Childcare Platform"
    "Service Offering"                       = ""
    "hidden-link: /app-insights-resource-id" = azurerm_application_insights.res-19.id
  }
  webdeploy_publish_basic_authentication_enabled = false
  identity {
    identity_ids = [var.azf_identity_id]
    type         = "UserAssigned"
  }
  site_config {
    api_management_api_id                   = var.api_management_api_id
    app_command_line                        = ""
    application_insights_connection_string  = azurerm_application_insights.res-19.connection_string
    application_insights_key                = azurerm_application_insights.res-19.instrumentation_key
    container_registry_use_managed_identity = false
    default_documents                       = ["Default.htm", "Default.html", "Default.asp", "index.htm", "index.html", "iisstart.htm", "default.aspx", "index.php"]
    elastic_instance_minimum                = 0
    health_check_path                       = ""
    http2_enabled                           = false
    load_balancing_mode                     = "LeastRequests"
    managed_pipeline_mode                   = "Integrated"
    minimum_tls_version                     = "1.2"
    remote_debugging_enabled                = false
    remote_debugging_version                = "VS2022"
    runtime_scale_monitoring_enabled        = false
    scm_minimum_tls_version                 = "1.2"
    scm_use_main_ip_restriction             = false
    use_32_bit_worker                       = false
    vnet_route_all_enabled                  = false
    websockets_enabled                      = false
    worker_count                            = 1
    cors {
      allowed_origins     = ["https://portal.azure.com"]
      support_credentials = true
    }
  }
}

resource "azurerm_function_app_function" "res-15" {
  config_json = jsonencode({
    bindings = [{
      authLevel = "anonymous"
      direction = "in"
      methods   = ["get"]
      name      = "req"
      route     = "health"
      type      = "httpTrigger"
      }, {
      direction = "out"
      name      = "res"
      type      = "http"
    }]
  })
  enabled         = true
  function_app_id = azurerm_function_app_flex_consumption.res-11.id
  name            = "health"
}

resource "azurerm_function_app_function" "res-16" {
  config_json = jsonencode({
    bindings = [{
      authLevel = "anonymous"
      direction = "in"
      methods   = ["get"]
      name      = "req"
      route     = "api/spatial-query"
      type      = "httpTrigger"
      }, {
      direction = "out"
      name      = "res"
      type      = "http"
    }]
  })
  enabled         = true
  function_app_id = azurerm_function_app_flex_consumption.res-11.id
  name            = "spatial-query"
}

resource "azurerm_app_service_custom_hostname_binding" "res-17" {
  app_service_name    = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  hostname            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01-gqergngzg3hwcdcw.uksouth-01.azurewebsites.net"
  resource_group_name = azurerm_resource_group.res-0.name
  depends_on = [
    azurerm_function_app_flex_consumption.res-11,
  ]
}

resource "azurerm_monitor_action_group" "res-18" {
  enabled             = true
  location            = "global"
  name                = "Application Insights Smart Detection"
  resource_group_name = azurerm_resource_group.res-0.name
  short_name          = "SmartDetect"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  arm_role_receiver {
    name                    = "Monitoring Contributor"
    role_id                 = "749f88d5-cbae-40b8-bcfc-e573ddc772fa"
    use_common_alert_schema = true
  }
  arm_role_receiver {
    name                    = "Monitoring Reader"
    role_id                 = "43d0d8ad-25c7-4714-9337-8ba259a9fe05"
    use_common_alert_schema = true
  }
}

resource "azurerm_application_insights" "res-19" {
  application_type                     = "web"
  daily_data_cap_in_gb                 = 100
  daily_data_cap_notifications_enabled = true
  force_customer_storage_for_profiler  = false
  internet_ingestion_enabled           = true
  internet_query_enabled               = true
  ip_masking_enabled                   = true
  local_authentication_enabled         = true
  location                             = var.region
  name                                 = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  resource_group_name                  = azurerm_resource_group.res-0.name
  retention_in_days                    = 90
  sampling_percentage                  = 0
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  workspace_id = var.log_analytics_workspace_id
}
