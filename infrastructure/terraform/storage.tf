resource "azurerm_resource_group" "storage" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-storage"
  tags = {
    Environment = var.environment_tag
    Product     = "Childcare Platform"
  }
}

resource "azurerm_storage_account" "site-data" {
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
  name                              = "cccepfdatastore${var.environment_prefix}${random_id.unique_suffix.hex}"
  nfsv3_enabled                     = false
  public_network_access_enabled     = false
  queue_encryption_key_type         = "Service"
  resource_group_name               = azurerm_resource_group.storage.name
  sftp_enabled                      = false
  shared_access_key_enabled         = true
  table_encryption_key_type         = "Service"
  tags = {
    Environment        = var.environment_tag
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  blob_properties {
    last_access_time_enabled = false
    versioning_enabled       = true
    change_feed_enabled      = true

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


resource "azurerm_storage_container" "provider-container" {
  container_access_type = "private"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-provider-data-01"
  storage_account_id    = azurerm_storage_account.site-data.id
}

resource "azurerm_storage_container" "source-data-container" {
  container_access_type = "blob"
  metadata              = {}
  name                  = "${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-source-data-01"
  storage_account_id    = azurerm_storage_account.site-data.id
}

resource "azurerm_storage_account_static_website" "staticsite" {
  storage_account_id = azurerm_storage_account.site-data.id
  index_document     = "index.html"
  error_404_document = "index.html"
}

resource "azurerm_storage_management_policy" "site-data-lifecycle" {
  storage_account_id = azurerm_storage_account.site-data.id

  rule {
    name    = "expire-old-blob-versions"
    enabled = true

    filters {
      blob_types = ["blockBlob"]
      prefix_match = [
        azurerm_storage_container.provider-container.name,
        azurerm_storage_container.source-data-container.name,
      ]
    }

    actions {
      version {
        delete_after_days_since_creation = 30
      }
    }
  }
}
