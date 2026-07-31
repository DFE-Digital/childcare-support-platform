include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/preprod.hcl"))
}

dependency "storage" {
  config_path = "../storage"

  mock_outputs = {
    vite_bucket_id          = "mock-vite-bucket"
    vite_bucket_arn         = "arn:aws:s3:::mock-vite-bucket"
    oac_id                  = "mock-oac-id"
    provider_data_bucket_id = "mock-provider-data-bucket"
    provider_data_oac_id    = "mock-provider-data-oac-id"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "security" {
  config_path = "../security"

  mock_outputs = {
    waf_cloudfront_arn = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/mock/mock-id"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "dns" {
  config_path = "../dns"

  mock_outputs = {
    certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/mock-cert-id"
    zone_id         = "MOCKZONEID"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "compute" {
  config_path = "../compute"

  mock_outputs = {
    api_gateway_id    = "mock-api-id"
    api_key_ssm_param = "/beststartinlife/preprod/api-key"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

generate "provider_us_east_1" {
  path      = "provider_us_east_1.tf"
  if_exists = "overwrite"
  contents  = <<-EOF
    provider "aws" {
      alias  = "us_east_1"
      region = "us-east-1"
    }
  EOF
}

terraform {
  source = "../../../modules//cdn"
}

inputs = {
  project                 = local.common.locals.project_name
  environment             = local.env_vars.locals.environment
  vite_bucket_id          = dependency.storage.outputs.vite_bucket_id
  vite_bucket_arn         = dependency.storage.outputs.vite_bucket_arn
  oac_id                  = dependency.storage.outputs.oac_id
  provider_data_bucket_id = dependency.storage.outputs.provider_data_bucket_id
  provider_data_oac_id    = dependency.storage.outputs.provider_data_oac_id
  waf_cloudfront_arn      = dependency.security.outputs.waf_cloudfront_arn
  domain_name             = "bsil-preprod.10ds.cabinetoffice.gov.uk"
  certificate_arn         = dependency.dns.outputs.certificate_arn
  route53_zone_id         = dependency.dns.outputs.zone_id
  api_gateway_id          = dependency.compute.outputs.api_gateway_id
  api_gateway_stage       = local.env_vars.locals.environment
  api_key_ssm_param       = dependency.compute.outputs.api_key_ssm_param

  basic_auth_enabled        = true
  basic_auth_ssm_user_param = "/beststartinlife/preprod/basic-auth/user"
  basic_auth_ssm_pass_param = "/beststartinlife/preprod/basic-auth/pass"

  # PostHog reverse proxy — see dev/cdn/terragrunt.hcl for rationale.
  posthog_proxy_enabled = true
}
