resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-edge"
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}

resource "azurerm_cdn_frontdoor_profile" "res-45" {
  name                     = "${var.subscription_prefix}${var.environment_prefix}afd-${local.location_prefix}-frontdoor-01"
  resource_group_name      = azurerm_resource_group.res-0.name
  response_timeout_seconds = 60
  sku_name                 = "Premium_AzureFrontDoor"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  identity {
    identity_ids = [var.frontdoor_identity_id]
    type         = "UserAssigned"
  }
}

resource "azurerm_cdn_frontdoor_endpoint" "res-46" {
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.res-45.id
  enabled                  = true
  name                     = "bsil-frontend"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
}

resource "azurerm_cdn_frontdoor_route" "res-47" {
  cdn_frontdoor_custom_domain_ids = []
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.res-46.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.res-48.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.res-49.id]
  cdn_frontdoor_origin_path       = ""
  cdn_frontdoor_rule_set_ids      = [azurerm_cdn_frontdoor_rule_set.res-54.id, azurerm_cdn_frontdoor_rule_set.res-56.id]
  enabled                         = true
  forwarding_protocol             = "MatchRequest"
  https_redirect_enabled          = true
  link_to_default_domain          = true
  name                            = "default-route"
  patterns_to_match               = ["/*"]
  supported_protocols             = ["Http", "Https"]
}

resource "azurerm_cdn_frontdoor_origin_group" "res-48" {
  cdn_frontdoor_profile_id                                  = azurerm_cdn_frontdoor_profile.res-45.id
  name                                                      = "default-origin-group-5b5349a1"
  restore_traffic_time_to_healed_or_new_endpoint_in_minutes = 0
  session_affinity_enabled                                  = false
  health_probe {
    interval_in_seconds = 100
    path                = "/"
    protocol            = "Https"
    request_type        = "HEAD"
  }
  load_balancing {
    additional_latency_in_milliseconds = 50
    sample_size                        = 4
    successful_samples_required        = 3
  }
}

resource "azurerm_cdn_frontdoor_origin" "res-49" {
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.res-48.id
  certificate_name_check_enabled = true
  enabled                        = true
  host_name                      = var.storage_primary_web_host
  http_port                      = 80
  https_port                     = 443
  name                           = "staticweb"
  origin_host_header             = var.storage_primary_web_host
  priority                       = 1
  weight                         = 1000
  private_link {
    location               = var.region
    private_link_target_id = var.storage_account_id
    request_message        = "The request is from storage account ${var.storage_account_name}"
    target_type            = "web"
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "res-50" {
  cdn_frontdoor_profile_id                                  = azurerm_cdn_frontdoor_profile.res-45.id
  name                                                      = "${var.subscription_prefix}${var.environment_prefix}og-${local.location_prefix}-azf-sis-01"
  restore_traffic_time_to_healed_or_new_endpoint_in_minutes = 0
  session_affinity_enabled                                  = false
  health_probe {
    interval_in_seconds = 100
    path                = "/"
    protocol            = "Http"
    request_type        = "HEAD"
  }
  load_balancing {
    additional_latency_in_milliseconds = 50
    sample_size                        = 4
    successful_samples_required        = 3
  }
}

resource "azurerm_cdn_frontdoor_origin" "res-51" {
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.res-50.id
  certificate_name_check_enabled = true
  enabled                        = true
  host_name                      = var.function_app_default_hostname
  http_port                      = 80
  https_port                     = 443
  name                           = "${var.subscription_prefix}${var.environment_prefix}origin-${local.location_prefix}-azf-sis-01"
  origin_host_header             = var.function_app_default_hostname
  priority                       = 1
  weight                         = 1000
  private_link {
    location               = var.region
    private_link_target_id = var.function_app_id
    request_message        = "The request is from Front Door to the spatial index service function app"
    target_type            = "sites"
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "res-52" {
  cdn_frontdoor_profile_id                                  = azurerm_cdn_frontdoor_profile.res-45.id
  name                                                      = "${var.subscription_prefix}${var.environment_prefix}og-${local.location_prefix}-runtime-data-01"
  restore_traffic_time_to_healed_or_new_endpoint_in_minutes = 0
  session_affinity_enabled                                  = false
  health_probe {
    interval_in_seconds = 100
    path                = "/"
    protocol            = "Http"
    request_type        = "HEAD"
  }
  load_balancing {
    additional_latency_in_milliseconds = 50
    sample_size                        = 4
    successful_samples_required        = 3
  }
}

resource "azurerm_cdn_frontdoor_origin" "res-53" {
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.res-52.id
  certificate_name_check_enabled = true
  enabled                        = true
  host_name                      = var.storage_primary_blob_host
  http_port                      = 80
  https_port                     = 443
  name                           = "${var.subscription_prefix}${var.environment_prefix}origin-${local.location_prefix}-runtime-data-01"
  origin_host_header             = var.storage_primary_blob_host
  priority                       = 1
  weight                         = 1000
}

resource "azurerm_cdn_frontdoor_rule_set" "res-54" {
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.res-45.id
  name                     = "MapApiRequestToFunctionApp"
}

resource "azurerm_cdn_frontdoor_rule" "res-55" {
  behaviour_on_match        = "Continue"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.res-54.id
  name                      = "MapApiRequestToFunctionApp"
  order                     = 100
  actions {
    route_configuration_override {
      caching {
        behaviour           = "Disabled"
        compression_enabled = false
      }
      origin_group {
        cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.res-50.id
        forwarding_protocol           = "MatchRequest"
      }
    }
    url_rewrite {
      destination_path                = "/api"
      preserve_unmatched_path_enabled = true
      source_pattern                  = "/api"
    }
  }
  conditions {
    request_path {
      values     = ["/api/", "/health"]
      operator   = "BeginsWith"
      transforms = []
    }
  }
}

resource "azurerm_cdn_frontdoor_rule_set" "res-56" {
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.res-45.id
  name                     = "MapDataRequestToRuntimeContainer"
}

resource "azurerm_cdn_frontdoor_rule" "res-57" {
  behaviour_on_match        = "Continue"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.res-56.id
  name                      = "MapDataRequestToRuntimeContainer"
  order                     = 100
  actions {
    route_configuration_override {
      caching {
        behaviour           = "Disabled"
        compression_enabled = false
      }
      origin_group {
        cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.res-52.id
        forwarding_protocol           = "MatchRequest"
      }
    }
    url_rewrite {
      destination_path                = "/${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-source-data-01/app"
      preserve_unmatched_path_enabled = true
      source_pattern                  = "/data"
    }
  }
  conditions {
    request_path {
      values     = ["/data/"]
      operator   = "BeginsWith"
      transforms = []
    }
  }
}

resource "azurerm_private_endpoint" "res-58" {
  custom_network_interface_name = "${var.subscription_prefix}${var.environment_prefix}nic-${local.location_prefix}-storage-endpoint-01"
  location                      = var.region
  name                          = "${var.subscription_prefix}${var.environment_prefix}pe-${local.location_prefix}-storage-endpoint-01"
  resource_group_name           = azurerm_resource_group.res-0.name
  subnet_id                     = var.frontend_subnet_id
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  private_service_connection {
    is_manual_connection           = false
    name                           = "${var.subscription_prefix}${var.environment_prefix}pe-${local.location_prefix}-storage-endpoint-01"
    private_connection_resource_id = var.storage_account_id
    subresource_names              = ["blob"]
  }
}

resource "azurerm_private_endpoint" "function_app" {
  custom_network_interface_name = "${var.subscription_prefix}${var.environment_prefix}nic-${local.location_prefix}-function-endpoint-01"
  location                      = var.region
  name                          = "${var.subscription_prefix}${var.environment_prefix}pe-${local.location_prefix}-function-endpoint-01"
  resource_group_name           = azurerm_resource_group.res-0.name
  subnet_id                     = var.frontend_subnet_id
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  private_service_connection {
    is_manual_connection           = false
    name                           = "${var.subscription_prefix}${var.environment_prefix}pe-${local.location_prefix}-function-endpoint-01"
    private_connection_resource_id = var.function_app_id
    subresource_names              = ["sites"]
  }
}
