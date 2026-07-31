# Dev environment - values populated after running terraform/bootstrap for dev account
inputs = {
  environment = "dev"
  aws_region  = "eu-west-2"

  aws_account_id             = "146072879673"
  tfstate_bucket             = "bsil-dev-tfstate"
  tfstate_lock_table         = "bsil-dev-tfstate-lock"
  # Unset for local runs - bootstrap role has direct S3/DynamoDB access.
  # Set to "arn:aws:iam::146072879673:role/TerragruntDeployRole" in CI/CD.
  terragrunt_deploy_role_arn = ""
  github_actions_role_arn    = "arn:aws:iam::146072879673:role/GitHubActionsDeployRole"
}
