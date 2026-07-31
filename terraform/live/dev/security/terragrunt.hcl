include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/dev.hcl"))
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id = "vpc-00000000000000000"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

terraform {
  source = "../../../modules//security"
}

# The security module requires a us-east-1 provider alias for the CloudFront WAF.
# The root terragrunt.hcl generates provider.tf (default eu-west-2).
# This generates a second file with the aliased provider.
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

inputs = {
  project     = local.common.locals.project_name
  environment = local.env_vars.locals.environment
  vpc_id      = dependency.vpc.outputs.vpc_id
}
