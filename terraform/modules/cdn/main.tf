terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 6.0"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

locals {
  tags = {
    Project     = var.project
    Environment = var.environment
  }

  s3_origin_id             = "s3-vite-${var.environment}"
  s3_provider_origin_id    = "s3-provider-data-${var.environment}"
  apigw_origin_id          = "apigw-${var.environment}"
  posthog_ingest_origin_id = "posthog-ingest-${var.environment}"
  posthog_assets_origin_id = "posthog-assets-${var.environment}"

  api_gateway_enabled = var.api_gateway_id != ""

  # Gate the function_association separately from the function itself so
  # disabling auth is a clean two-step rollout (dissociate, then destroy).
  basic_auth_associated = var.basic_auth_associated == null ? var.basic_auth_enabled : var.basic_auth_associated
}

# -----------------------------------------------------------------------------
# SSM — read basic auth credentials at plan time (never stored in state values)
# -----------------------------------------------------------------------------

data "aws_ssm_parameter" "basic_auth_user" {
  count           = var.basic_auth_enabled ? 1 : 0
  provider        = aws.us_east_1
  name            = var.basic_auth_ssm_user_param
  with_decryption = true
}

data "aws_ssm_parameter" "basic_auth_pass" {
  count           = var.basic_auth_enabled ? 1 : 0
  provider        = aws.us_east_1
  name            = var.basic_auth_ssm_pass_param
  with_decryption = true
}

# -----------------------------------------------------------------------------
# CloudFront Function — Basic Auth (optional, gated on var.basic_auth_enabled)
# Credentials are baked in as a base64 string at plan time from SSM.
# No IAM role, no runtime AWS calls, sub-millisecond execution.
# -----------------------------------------------------------------------------

resource "aws_cloudfront_function" "basic_auth" {
  count = var.basic_auth_enabled ? 1 : 0

  name    = "${var.project}-${var.environment}${var.name_suffix != "" ? "-${var.name_suffix}" : ""}-basic-auth"
  runtime = "cloudfront-js-2.0"
  publish = true

  code = templatefile("${path.module}/lambda_basic_auth/basic_auth.js.tpl", {
    expected_b64 = base64encode(
      "${data.aws_ssm_parameter.basic_auth_user[0].value}:${data.aws_ssm_parameter.basic_auth_pass[0].value}"
    )
  })
}

# -----------------------------------------------------------------------------
# SSM — read API key at plan time (eu-west-2, stored by compute module)
# Baked into a CloudFront Function so the value is never visible to clients.
# -----------------------------------------------------------------------------

data "aws_ssm_parameter" "api_key" {
  count           = local.api_gateway_enabled ? 1 : 0
  name            = var.api_key_ssm_param
  with_decryption = true
}

# -----------------------------------------------------------------------------
# CloudFront Function — API key injector (gated on api_gateway_id being set)
# Injects x-api-key on every /api/* viewer request before forwarding to origin.
# -----------------------------------------------------------------------------

resource "aws_cloudfront_function" "inject_api_key" {
  count = local.api_gateway_enabled ? 1 : 0

  name    = "${var.project}-${var.environment}${var.name_suffix != "" ? "-${var.name_suffix}" : ""}-inject-api-key"
  runtime = "cloudfront-js-2.0"
  publish = true

  code = templatefile("${path.module}/functions/inject_api_key.js.tpl", {
    api_key = data.aws_ssm_parameter.api_key[0].value
  })
}

# -----------------------------------------------------------------------------
# CloudFront Function — PostHog URI rewriter (viewer-request)
# Strips the /ingest prefix so requests reach PostHog at the root of its host.
# Sub-millisecond, no IAM, runs at every edge.
# -----------------------------------------------------------------------------

resource "aws_cloudfront_function" "rewrite_posthog" {
  count = var.posthog_proxy_enabled ? 1 : 0

  name    = "${var.project}-${var.environment}${var.name_suffix != "" ? "-${var.name_suffix}" : ""}-rewrite-posthog"
  runtime = "cloudfront-js-2.0"
  publish = true

  code = file("${path.module}/functions/rewrite_posthog.js.tpl")
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = var.price_class
  web_acl_id          = var.waf_cloudfront_arn
  aliases             = var.domain_name != "" ? [var.domain_name] : []

  origin {
    domain_name              = "${var.vite_bucket_id}.s3.eu-west-2.amazonaws.com"
    origin_id                = local.s3_origin_id
    origin_access_control_id = var.oac_id
  }

  origin {
    domain_name              = "${var.provider_data_bucket_id}.s3.eu-west-2.amazonaws.com"
    origin_id                = local.s3_provider_origin_id
    origin_access_control_id = var.provider_data_oac_id
  }

  # API Gateway origin — only wired in when api_gateway_id is provided
  dynamic "origin" {
    for_each = local.api_gateway_enabled ? [1] : []
    content {
      domain_name = "${var.api_gateway_id}.execute-api.eu-west-2.amazonaws.com"
      origin_id   = local.apigw_origin_id
      origin_path = "/${var.api_gateway_stage}"

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # PostHog ingest origin — receives /ingest/* (events, decide, capture, etc.)
  dynamic "origin" {
    for_each = var.posthog_proxy_enabled ? [1] : []
    content {
      domain_name = var.posthog_ingest_host
      origin_id   = local.posthog_ingest_origin_id

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # PostHog static-assets origin — serves the posthog-js bundle and feature flags JS
  dynamic "origin" {
    for_each = var.posthog_proxy_enabled ? [1] : []
    content {
      domain_name = var.posthog_assets_host
      origin_id   = local.posthog_assets_origin_id

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # /api/* — routed to API Gateway; x-api-key injected by CloudFront Function
  dynamic "ordered_cache_behavior" {
    for_each = local.api_gateway_enabled ? [1] : []
    content {
      path_pattern           = "/api/*"
      allowed_methods        = ["GET", "HEAD"]
      cached_methods         = ["GET", "HEAD"]
      target_origin_id       = local.apigw_origin_id
      viewer_protocol_policy = "redirect-to-https"
      compress               = true

      # Pass all query params (spatial query uses many) and forward the injected API key
      forwarded_values {
        query_string = true
        headers      = ["x-api-key"]

        cookies {
          forward = "none"
        }
      }

      # Never cache API responses — every spatial query is unique
      min_ttl     = 0
      default_ttl = 0
      max_ttl     = 0

      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.inject_api_key[0].arn
      }
    }
  }

  # /ingest/static/* — PostHog static assets (posthog-js bundle, decide JSON).
  # Cacheable: PostHog versions URLs by content hash, so long TTLs are safe.
  dynamic "ordered_cache_behavior" {
    for_each = var.posthog_proxy_enabled ? [1] : []
    content {
      path_pattern           = "/ingest/static/*"
      allowed_methods        = ["GET", "HEAD", "OPTIONS"]
      cached_methods         = ["GET", "HEAD"]
      target_origin_id       = local.posthog_assets_origin_id
      viewer_protocol_policy = "redirect-to-https"
      compress               = true

      forwarded_values {
        query_string = true
        cookies { forward = "none" }
      }

      min_ttl     = 0
      default_ttl = 86400
      max_ttl     = 31536000

      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.rewrite_posthog[0].arn
      }
    }
  }

  # /ingest/* — PostHog event ingest, capture, decide, etc.
  # Never cached — every event must reach PostHog. Forward all query strings
  # and the small set of headers PostHog uses to identify the request.
  dynamic "ordered_cache_behavior" {
    for_each = var.posthog_proxy_enabled ? [1] : []
    content {
      path_pattern           = "/ingest/*"
      allowed_methods        = ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
      cached_methods         = ["GET", "HEAD"]
      target_origin_id       = local.posthog_ingest_origin_id
      viewer_protocol_policy = "redirect-to-https"
      compress               = true

      forwarded_values {
        query_string = true
        headers      = ["Referer", "Origin"]
        cookies { forward = "none" }
      }

      min_ttl     = 0
      default_ttl = 0
      max_ttl     = 0

      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.rewrite_posthog[0].arn
      }
    }
  }

  # /data/* — served from the provider-data bucket (provider JSON, postcodes, tiles, sis_schema)
  # S3 objects carry Cache-Control: no-cache so browsers always revalidate.
  # Edge TTL is short; cdn/invalidate clears it on each deploy.
  ordered_cache_behavior {
    path_pattern           = "/data/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.s3_provider_origin_id
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    min_ttl                = 0
    default_ttl            = 60
    max_ttl                = 300

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.s3_origin_id
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    dynamic "function_association" {
      for_each = local.basic_auth_associated ? [1] : []
      content {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.basic_auth[0].arn
      }
    }
  }

  # SPA routing - S3 returns 403/404 for paths CloudFront doesn't know about;
  # redirect both to index.html so the client-side router can handle them.
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.certificate_arn == "" ? true : null
    acm_certificate_arn            = var.certificate_arn != "" ? var.certificate_arn : null
    ssl_support_method             = var.certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = var.certificate_arn != "" ? "TLSv1.2_2021" : null
  }

  tags = local.tags
}

# Route53 alias A record pointing the custom domain at CloudFront
resource "aws_route53_record" "cloudfront_alias" {
  count = var.domain_name != "" && var.route53_zone_id != "" ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
