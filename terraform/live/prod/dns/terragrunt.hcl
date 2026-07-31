include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/prod.hcl"))
}

# ACM certificate must be in us-east-1 for CloudFront
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
  source = "../../../modules//dns"
}

inputs = {
  project     = local.common.locals.project_name
  environment = local.env_vars.locals.environment
  domain_name = "bsil.10ds.cabinetoffice.gov.uk"
}
