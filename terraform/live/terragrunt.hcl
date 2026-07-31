# -----------------------------------------------------------------------------
# Root Terragrunt config - inherited by all environments via include {}
# -----------------------------------------------------------------------------

locals {
  common_vars      = read_terragrunt_config(find_in_parent_folders("common.tfvars"))
  env_vars         = read_terragrunt_config(find_in_parent_folders("env.tfvars"))
  env              = basename(dirname(find_in_parent_folders("env.tfvars")))
  deploy_role_arn  = try(local.env_vars.inputs.terragrunt_deploy_role_arn, "")
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite"
  contents  = <<-EOF
    provider "aws" {
      region = "${local.common_vars.inputs.aws_region}"

      default_tags {
        tags = {
          Environment = "${local.env_vars.inputs.environment}"
          Project     = "${local.common_vars.inputs.project}"
          ManagedBy   = "terragrunt"
        }
      }
    }
  EOF
}

# Per-account state bucket - created by terraform/bootstrap for each account
remote_state {
  backend = "s3"
  config = {
    bucket         = local.env_vars.inputs.tfstate_bucket
    key            = "beststartinlife/${path_relative_to_include()}/terraform.tfstate"
    region         = local.env_vars.inputs.aws_region
    dynamodb_table = local.env_vars.inputs.tfstate_lock_table
    encrypt        = true

    # Only assume the deploy role when one is configured (CI/CD). Local runs
    # using the bootstrap profile skip this and use ambient credentials directly.
    assume_role = local.deploy_role_arn != "" ? { role_arn = local.deploy_role_arn } : null
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
}

inputs = merge(
  local.common_vars.inputs,
  local.env_vars.inputs,
)
