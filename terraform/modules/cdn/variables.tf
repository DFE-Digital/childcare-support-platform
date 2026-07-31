variable "project" {
  description = "Project name, used in tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "vite_bucket_id" {
  description = "S3 bucket ID (name) of the vite-build-outputs bucket"
  type        = string
}

variable "vite_bucket_arn" {
  description = "S3 bucket ARN of the vite-build-outputs bucket"
  type        = string
}

variable "oac_id" {
  description = "CloudFront Origin Access Control ID for the vite-build-outputs bucket (from storage module)"
  type        = string
}

variable "provider_data_bucket_id" {
  description = "S3 bucket ID (name) of the provider-data bucket"
  type        = string
}

variable "provider_data_oac_id" {
  description = "CloudFront Origin Access Control ID for the provider-data bucket (from storage module)"
  type        = string
}

variable "waf_cloudfront_arn" {
  description = "ARN of the us-east-1 WAFv2 WebACL to associate with the distribution"
  type        = string
}

variable "price_class" {
  description = "CloudFront price class. PriceClass_100 covers EU + North America only"
  type        = string
  default     = "PriceClass_100"
}

variable "domain_name" {
  description = "Custom domain name for the CloudFront distribution (e.g. bsil.10ds.cabinetoffice.gov.uk). Leave empty to use the default CloudFront domain."
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN (must be in us-east-1) for the custom domain. Required when domain_name is set."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID — used to create the A alias record for the custom domain. Required when domain_name is set."
  type        = string
  default     = ""
}

variable "basic_auth_enabled" {
  description = "Provision the CloudFront basic auth function and supporting SSM data sources. To remove auth, do this in two applies: first set basic_auth_associated = false, then set basic_auth_enabled = false. CloudFront rejects DeleteFunction while the distribution still binds the function, so the dissociation must propagate (Status: Deployed) before the function is destroyed."
  type        = bool
  default     = false
}

variable "basic_auth_associated" {
  description = "Whether the CloudFront distribution's default cache behaviour binds the basic auth function. Defaults to basic_auth_enabled. Use this to dissociate the function in one apply ahead of destroying it in the next, avoiding the FunctionInUse race."
  type        = bool
  default     = null

  validation {
    condition     = !(coalesce(var.basic_auth_associated, false) && !var.basic_auth_enabled)
    error_message = "basic_auth_associated cannot be true when basic_auth_enabled is false (the function would not exist)."
  }
}

variable "basic_auth_ssm_user_param" {
  description = "SSM Parameter Store path for the basic auth username. Create the SecureString manually in us-east-1 before applying."
  type        = string
  default     = ""
}

variable "basic_auth_ssm_pass_param" {
  description = "SSM Parameter Store path for the basic auth password. Create the SecureString manually in us-east-1 before applying."
  type        = string
  default     = ""
}

variable "api_gateway_id" {
  description = "REST API ID of the API Gateway to expose at /api/*. Leave empty to skip wiring API Gateway into CloudFront."
  type        = string
  default     = ""
}

variable "api_gateway_stage" {
  description = "API Gateway stage name (e.g. 'dev'). Used as the origin_path prefix so CloudFront forwards /api/X as /{stage}/api/X to API Gateway."
  type        = string
  default     = ""
}

variable "api_key_ssm_param" {
  description = "SSM SecureString path for the API Gateway key value (stored by the compute module). Read at plan time and baked into a CloudFront Function so the key is never visible to browser clients. Required when api_gateway_id is set."
  type        = string
  default     = ""
}

variable "name_suffix" {
  description = "Optional suffix appended to CloudFront Function names to disambiguate multiple distributions in the same environment."
  type        = string
  default     = ""
}

variable "posthog_proxy_enabled" {
  description = "Reverse-proxy PostHog through this CloudFront distribution. When true, /ingest/* is forwarded to eu.i.posthog.com and /ingest/static/* to eu-assets.i.posthog.com. Frontend should set api_host to /ingest."
  type        = bool
  default     = false
}

variable "posthog_ingest_host" {
  description = "PostHog ingest host (region-specific). Defaults to the EU cluster."
  type        = string
  default     = "eu.i.posthog.com"
}

variable "posthog_assets_host" {
  description = "PostHog static assets host (region-specific). Defaults to the EU cluster."
  type        = string
  default     = "eu-assets.i.posthog.com"
}
