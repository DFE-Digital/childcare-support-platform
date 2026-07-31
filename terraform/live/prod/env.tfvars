# Prod environment - values populated after running terraform/bootstrap for prod account
inputs = {
  environment = "prod"
  aws_region  = "eu-west-2"

  aws_account_id             = "522029197016"
  tfstate_bucket             = "bsil-prod-tfstate"
  tfstate_lock_table         = "bsil-prod-tfstate-lock"
  # Unset for local runs - bootstrap role has direct S3/DynamoDB access.
  # Set to "arn:aws:iam::522029197016:role/TerragruntDeployRole" in CI/CD.
  terragrunt_deploy_role_arn = ""
  github_actions_role_arn    = "arn:aws:iam::522029197016:role/GitHubActionsDeployRole"
}
