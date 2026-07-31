include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/prod.hcl"))
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-00000000000000000"
    private_subnet_ids = ["subnet-00000000000000000", "subnet-00000000000000001", "subnet-00000000000000002"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "security" {
  config_path = "../security"

  mock_outputs = {
    lambda_sg_id     = "sg-00000000000000000"
    runner_sg_id     = "sg-00000000000000001"
    waf_regional_arn = "arn:aws:wafv2:eu-west-2:123456789012:regional/webacl/mock/mock-id"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

terraform {
  source = "../../../modules//compute"
}

inputs = {
  project              = local.common.locals.project_name
  environment          = local.env_vars.locals.environment
  vpc_id               = dependency.vpc.outputs.vpc_id
  private_subnet_ids   = dependency.vpc.outputs.private_subnet_ids
  lambda_sg_id         = dependency.security.outputs.lambda_sg_id
  runner_sg_id         = dependency.security.outputs.runner_sg_id
  waf_regional_arn     = dependency.security.outputs.waf_regional_arn
  runner_instance_type = local.env_vars.locals.runner_instance_type
  github_org           = local.env_vars.locals.github_org
  github_repo          = local.env_vars.locals.github_repo
}
