moved {
  from = module.runtime.azurerm_resource_group.res-0
  to   = azurerm_resource_group.runtime
}

resource "azurerm_resource_group" "runtime" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-runtime"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

moved {
  from = module.runtime.azurerm_storage_account.res-2
  to   = azurerm_storage_account.storage
}

resource "azurerm_storage_account" "storage" {
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
  name                              = "${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${random_id.unique_suffix.hex}"
  nfsv3_enabled                     = false
  public_network_access_enabled     = true
  queue_encryption_key_type         = "Service"
  resource_group_name               = azurerm_resource_group.runtime.name
  sftp_enabled                      = false
  shared_access_key_enabled         = true
  table_encryption_key_type         = "Service"
  tags = {
    Environment        = var.environment_tag
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

moved {
  from = module.runtime.azurerm_storage_container.res-4
  to   = azurerm_storage_container.webjobs-hosts
}

resource "azurerm_storage_container" "webjobs-hosts" {
  container_access_type = "private"
  metadata              = {}
  name                  = "azure-webjobs-hosts"
  storage_account_id    = azurerm_storage_account.storage.id
}

moved {
  from = module.runtime.azurerm_storage_container.res-5
  to   = azurerm_storage_container.webjobs-secrets
}

resource "azurerm_storage_container" "webjobs-secrets" {
  container_access_type = "private"
  metadata              = {}
  name                  = "azure-webjobs-secrets"
  storage_account_id    = azurerm_storage_account.storage.id
}

moved {
  from = module.runtime.azurerm_storage_container.res-6
  to   = azurerm_storage_container.runtime-storage
}

resource "azurerm_storage_container" "runtime-storage" {
  container_access_type = "private"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${random_id.unique_suffix.hex}"
  storage_account_id    = azurerm_storage_account.storage.id
}

moved {
  from = module.runtime.azurerm_service_plan.res-10
  to   = azurerm_service_plan.service-plan
}

resource "azurerm_service_plan" "service-plan" {
  location                        = var.region
  maximum_elastic_worker_count    = 1
  name                            = "ASP-${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime-${random_id.unique_suffix.hex}"
  os_type                         = "Linux"
  per_site_scaling_enabled        = false
  premium_plan_auto_scale_enabled = false
  resource_group_name             = azurerm_resource_group.runtime.name
  sku_name                        = "FC1"
  tags = {
    Environment        = var.environment_tag
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  zone_balancing_enabled = false
}

moved {
  from = module.runtime.azurerm_function_app_flex_consumption.res-11
  to   = azurerm_function_app_flex_consumption.consumption-plan
}

resource "azurerm_function_app_flex_consumption" "consumption-plan" {
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
  public_network_access_enabled      = false
  resource_group_name                = azurerm_resource_group.runtime.name
  runtime_name                       = "custom"
  runtime_version                    = "1.0"
  service_plan_id                    = azurerm_service_plan.service-plan.id
  storage_access_key                 = azurerm_storage_account.storage.primary_access_key
  storage_authentication_type        = "StorageAccountConnectionString"
  storage_container_endpoint         = "https://${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${random_id.unique_suffix.hex}.blob.core.windows.net/${var.subscription_prefix}${var.environment_prefix}rg${local.location_prefix}runtime${random_id.unique_suffix.hex}"
  storage_container_type             = "blobContainer"
  tags = {
    Environment                              = var.environment_tag
    Product                                  = "Childcare Platform"
    "Service Offering"                       = ""
    "hidden-link: /app-insights-resource-id" = azurerm_application_insights.application-insights.id
  }
  webdeploy_publish_basic_authentication_enabled = true
  identity {
    identity_ids = [azurerm_user_assigned_identity.azf-identity.id]
    type         = "UserAssigned"
  }
  site_config {
    app_command_line                        = ""
    application_insights_connection_string  = azurerm_application_insights.application-insights.connection_string
    application_insights_key                = azurerm_application_insights.application-insights.instrumentation_key
    container_registry_use_managed_identity = false
    default_documents                       = ["Default.htm", "Default.html", "Default.asp", "index.htm", "index.html", "iisstart.htm", "default.aspx", "index.php"]
    elastic_instance_minimum                = 0
    #health_check_path                       = ""
    http2_enabled                    = false
    load_balancing_mode              = "LeastRequests"
    managed_pipeline_mode            = "Integrated"
    minimum_tls_version              = "1.2"
    remote_debugging_enabled         = false
    remote_debugging_version         = "VS2022"
    runtime_scale_monitoring_enabled = false
    scm_minimum_tls_version          = "1.2"
    scm_use_main_ip_restriction      = false
    use_32_bit_worker                = false
    vnet_route_all_enabled           = false
    websockets_enabled               = false
    worker_count                     = 1
    cors {
      allowed_origins     = ["https://portal.azure.com"]
      support_credentials = true
    }
  }
}
