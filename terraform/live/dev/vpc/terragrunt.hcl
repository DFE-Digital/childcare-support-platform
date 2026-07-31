include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/dev.hcl"))
}

terraform {
  source = "../../../modules//vpc"
}

inputs = {
  project              = local.common.locals.project_name
  environment          = local.env_vars.locals.environment
  vpc_cidr             = local.env_vars.locals.vpc_cidr
  public_subnet_cidrs  = local.env_vars.locals.public_subnet_cidrs
  private_subnet_cidrs = local.env_vars.locals.private_subnet_cidrs
  create_nat_gateway   = local.env_vars.locals.create_nat_gateway
}
