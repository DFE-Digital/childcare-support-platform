resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-storage"
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}

resource "azurerm_storage_account" "res-1" {
  access_tier                       = "Hot"
  account_kind                      = "StorageV2"
  account_replication_type          = "RAGRS"
  account_tier                      = "Standard"
  allow_nested_items_to_be_public   = true
  cross_tenant_replication_enabled  = false
  default_to_oauth_authentication   = false
  dns_endpoint_type                 = "Standard"
  https_traffic_only_enabled        = true
  infrastructure_encryption_enabled = false
  is_hns_enabled                    = false
  large_file_share_enabled          = false
  local_user_enabled                = true
  location                          = var.region
  min_tls_version                   = "TLS1_2"
  name                              = "cccepfdatastore${var.environment_prefix}${var.unique_suffix}"
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
    container_delete_retention_policy {
      days = 7
    }
    delete_retention_policy {
      days                     = 7
      permanent_delete_enabled = false
    }
  }
  share_properties {
    retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "res-3" {
  container_access_type = "private"
  metadata              = {}
  name                  = "$web"
  storage_account_id    = azurerm_storage_account.res-1.id
}

resource "azurerm_storage_container" "res-4" {
  container_access_type = "private"
  metadata              = {}
  name                  = "insights-logs-frontdooraccesslog"
  storage_account_id    = azurerm_storage_account.res-1.id
}

resource "azurerm_storage_container" "res-5" {
  container_access_type = "private"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-provider-data-01"
  storage_account_id    = azurerm_storage_account.res-1.id
}

resource "azurerm_storage_container" "res-6" {
  container_access_type = "private"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-runtime-01"
  storage_account_id    = azurerm_storage_account.res-1.id
}

resource "azurerm_storage_container" "res-7" {
  container_access_type = "blob"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-source-data-01"
  storage_account_id    = azurerm_storage_account.res-1.id
}
