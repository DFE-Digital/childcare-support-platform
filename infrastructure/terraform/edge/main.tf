resource "random_password" "spatial_index_service_function_key" {
  length  = 40
  special = false
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "res-0" {
  location = var.region
  name     = "${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-edge"
  tags = {
    Environment = "Dev"
    Product     = "Childcare Platform"
  }
}

resource "azurerm_api_management" "res-1" {
  client_certificate_enabled    = false
  gateway_disabled              = false
  location                      = "ukwest"
  name                          = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  notification_sender_email     = "apimgmt-noreply@mail.windowsazure.com"
  public_network_access_enabled = true
  publisher_email               = "isaac.NAYLOR@education.gov.uk"
  publisher_name                = "Department for Education"
  resource_group_name           = azurerm_resource_group.res-0.name
  sku_name                      = "StandardV2_1"
  tags = {
    Environment        = "Dev"
    Product            = "Childcare Platform"
    "Service Offering" = ""
  }
  virtual_network_type = "None"
  zones                = []
  hostname_configuration {
    proxy {
      default_ssl_binding          = true
      host_name                    = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01.azure-api.net"
      negotiate_client_certificate = false
    }
  }
  identity {
    identity_ids = [var.apim_identity_id]
    type         = "UserAssigned"
  }
  protocols {
    http2_enabled = false
  }
  security {
    backend_ssl30_enabled                               = false
    backend_tls10_enabled                               = false
    backend_tls11_enabled                               = false
    frontend_ssl30_enabled                              = false
    frontend_tls10_enabled                              = false
    frontend_tls11_enabled                              = false
    tls_ecdhe_ecdsa_with_aes128_cbc_sha_ciphers_enabled = false
    tls_ecdhe_ecdsa_with_aes256_cbc_sha_ciphers_enabled = false
    tls_ecdhe_rsa_with_aes128_cbc_sha_ciphers_enabled   = false
    tls_ecdhe_rsa_with_aes256_cbc_sha_ciphers_enabled   = false
    tls_rsa_with_aes128_cbc_sha256_ciphers_enabled      = false
    tls_rsa_with_aes128_cbc_sha_ciphers_enabled         = false
    tls_rsa_with_aes128_gcm_sha256_ciphers_enabled      = false
    tls_rsa_with_aes256_cbc_sha256_ciphers_enabled      = false
    tls_rsa_with_aes256_cbc_sha_ciphers_enabled         = false
    tls_rsa_with_aes256_gcm_sha384_ciphers_enabled      = false
    triple_des_ciphers_enabled                          = false
  }
}

resource "azurerm_api_management_api" "res-2" {
  api_management_name   = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_type              = "http"
  description           = "Import from \"${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01\" Function App"
  display_name          = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  name                  = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  path                  = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  protocols             = ["https"]
  resource_group_name   = azurerm_resource_group.res-0.name
  revision              = "1"
  service_url           = ""
  subscription_required = false
  version               = ""
  version_set_id        = ""
  subscription_key_parameter_names {
    header = "Ocp-Apim-Subscription-Key"
    query  = "subscription-key"
  }
  depends_on = [
    azurerm_api_management.res-1,
  ]
}

resource "azurerm_api_management_api_operation" "res-3" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_name            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  description         = ""
  display_name        = "health"
  method              = "GET"
  operation_id        = "get-health"
  resource_group_name = azurerm_resource_group.res-0.name
  url_template        = "/health"
  request {
    description = ""
  }
  depends_on = [
    azurerm_api_management_api.res-2,
  ]
}

resource "azurerm_api_management_api_operation_policy" "res-4" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_name            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  operation_id        = "get-health"
  resource_group_name = azurerm_resource_group.res-0.name
  xml_content         = "<policies>\r\n\t<inbound>\r\n\t\t<base />\r\n\t\t<set-backend-service id=\"apim-generated-policy\" backend-id=\"${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01\" />\r\n\t</inbound>\r\n\t<backend>\r\n\t\t<base />\r\n\t</backend>\r\n\t<outbound>\r\n\t\t<base />\r\n\t</outbound>\r\n\t<on-error>\r\n\t\t<base />\r\n\t</on-error>\r\n</policies>"
  depends_on = [
    azurerm_api_management_api_operation.res-3,
  ]
}

resource "azurerm_api_management_api_operation" "res-5" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_name            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  description         = ""
  display_name        = "spatial-query"
  method              = "GET"
  operation_id        = "get-spatial-query"
  resource_group_name = azurerm_resource_group.res-0.name
  url_template        = "/api/spatial-query"
  request {
    description = ""
  }
  depends_on = [
    azurerm_api_management_api.res-2,
  ]
}

resource "azurerm_api_management_api_operation_policy" "res-6" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_name            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  operation_id        = "get-spatial-query"
  resource_group_name = azurerm_resource_group.res-0.name
  xml_content         = "<policies>\r\n\t<inbound>\r\n\t\t<base />\r\n\t\t<set-backend-service id=\"apim-generated-policy\" backend-id=\"${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01\" />\r\n\t</inbound>\r\n\t<backend>\r\n\t\t<base />\r\n\t</backend>\r\n\t<outbound>\r\n\t\t<base />\r\n\t</outbound>\r\n\t<on-error>\r\n\t\t<base />\r\n\t</on-error>\r\n</policies>"
  depends_on = [
    azurerm_api_management_api_operation.res-5,
  ]
}

resource "azurerm_api_management_api_policy" "res-7" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  api_name            = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  resource_group_name = azurerm_resource_group.res-0.name
  xml_content         = <<-XML
    <!--
        - Policies are applied in the order they appear.
        - Position <base/> inside a section to inherit policies from the outer scope.
        - Comments within policies are not preserved.
    -->
    <!-- Add policies as children to the <inbound>, <outbound>, <backend>, and <on-error> elements -->
    <policies>
    	<!-- Throttle, authorize, validate, cache, or transform the requests -->
    	<inbound>
    		<check-header name="X-Azure-FDID" failed-check-httpcode="403" failed-check-error-message="Invalid request." ignore-case="false">
    			<value>${azurerm_cdn_frontdoor_profile.res-45.resource_guid}</value>
    		</check-header>
    		<base />
    	</inbound>
    	<!-- Control if and how the requests are forwarded to services  -->
    	<backend>
    		<base />
    	</backend>
    	<!-- Customize the responses -->
    	<outbound>
    		<base />
    	</outbound>
    	<!-- Handle exceptions and customize error responses  -->
    	<on-error>
    		<base />
    	</on-error>
    </policies>
    XML
  depends_on = [
    azurerm_api_management_api.res-2,
  ]
}

resource "azurerm_api_management_backend" "res-8" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  description         = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  name                = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  protocol            = "http"
  resource_group_name = azurerm_resource_group.res-0.name
  resource_id         = "https://management.azure.com/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.subscription_prefix}${var.environment_prefix}rg-${local.location_prefix}-runtime/providers/Microsoft.Web/sites/${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01"
  url                 = "https://${var.function_app_default_hostname}"
  credentials {
    certificate = []
    header = {
      x-functions-key = "{{${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01-key}}"
    }
    query = {}
  }
  depends_on = [
    azurerm_api_management.res-1,
  ]
}

resource "azurerm_api_management_named_value" "res-17" {
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  display_name        = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01-key"
  name                = "${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01-key"
  resource_group_name = azurerm_resource_group.res-0.name
  secret              = true
  tags                = ["key", "function", "auto"]
  value               = random_password.spatial_index_service_function_key.result
  depends_on = [
    azurerm_api_management.res-1,
  ]
}

resource "azurerm_api_management_policy" "res-25" {
  api_management_id = azurerm_api_management.res-1.id
  xml_content       = "<!--\r\n    IMPORTANT:\r\n    - Policy elements can appear only within the <inbound>, <outbound>, <backend> section elements.\r\n    - Only the <forward-request> policy element can appear within the <backend> section element.\r\n    - To apply a policy to the incoming request (before it is forwarded to the backend service), place a corresponding policy element within the <inbound> section element.\r\n    - To apply a policy to the outgoing response (before it is sent back to the caller), place a corresponding policy element within the <outbound> section element.\r\n    - To add a policy position the cursor at the desired insertion point and click on the round button associated with the policy.\r\n    - To remove a policy, delete the corresponding policy statement from the policy document.\r\n    - Policies are applied in the order of their appearance, from the top down.\r\n-->\r\n<policies>\r\n\t<inbound></inbound>\r\n\t<backend>\r\n\t\t<forward-request />\r\n\t</backend>\r\n\t<outbound></outbound>\r\n</policies>"
}

resource "azurerm_api_management_subscription" "res-29" {
  allow_tracing       = false
  api_id              = azurerm_api_management_api_policy.res-7.id
  api_management_name = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01"
  display_name        = "SIS Subscription"
  primary_key         = "" # Masked sensitive attribute
  resource_group_name = azurerm_resource_group.res-0.name
  secondary_key       = "" # Masked sensitive attribute
  state               = "active"
  subscription_id     = "${var.subscription_prefix}${var.environment_prefix}sub-${local.location_prefix}-sis-sub-01"
  user_id             = "${azurerm_api_management.res-1.id}/users/1"
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
  host_name                      = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01.azure-api.net"
  http_port                      = 80
  https_port                     = 443
  name                           = "${var.subscription_prefix}${var.environment_prefix}origin-${local.location_prefix}-azf-sis-01"
  origin_host_header             = "${var.subscription_prefix}${var.environment_prefix}apim-ukw-sis-management-01.azure-api.net"
  priority                       = 1
  weight                         = 1000
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
  name                     = "MapApiRequestToApim"
}

resource "azurerm_cdn_frontdoor_rule" "res-55" {
  behavior_on_match         = "Continue"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.res-54.id
  name                      = "MapApiRequestToApim"
  order                     = 100
  actions {
    route_configuration_override_action {
      cache_behavior                = "Disabled"
      cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.res-50.id
      compression_enabled           = false
      forwarding_protocol           = "MatchRequest"
      query_string_parameters       = []
    }
    url_rewrite_action {
      destination             = "/${var.subscription_prefix}${var.environment_prefix}azf-${local.location_prefix}-spatial-index-service-01/api"
      preserve_unmatched_path = true
      source_pattern          = "/api"
    }
  }
  conditions {
    url_path_condition {
      match_values     = ["/api/", "/health"]
      negate_condition = false
      operator         = "BeginsWith"
      transforms       = []
    }
  }
}

resource "azurerm_cdn_frontdoor_rule_set" "res-56" {
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.res-45.id
  name                     = "MapDataRequestToRuntimeContainer"
}

resource "azurerm_cdn_frontdoor_rule" "res-57" {
  behavior_on_match         = "Continue"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.res-56.id
  name                      = "MapDataRequestToRuntimeContainer"
  order                     = 100
  actions {
    route_configuration_override_action {
      cache_behavior                = "Disabled"
      cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.res-52.id
      compression_enabled           = false
      forwarding_protocol           = "MatchRequest"
      query_string_parameters       = []
    }
    url_rewrite_action {
      destination             = "/${var.subscription_prefix}${var.environment_prefix}bc-${local.location_prefix}-source-data-01/app"
      preserve_unmatched_path = true
      source_pattern          = "/data"
    }
  }
  conditions {
    url_path_condition {
      match_values     = ["/data/"]
      negate_condition = false
      operator         = "BeginsWith"
      transforms       = []
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
