# Preprod environment - values populated after running terraform/bootstrap for preprod account
inputs = {
  environment = "preprod"
  aws_region  = "eu-west-2"

  aws_account_id             = "135133927908"
  tfstate_bucket             = "bsil-preprod-tfstate"
  tfstate_lock_table         = "bsil-preprod-tfstate-lock"
  # Unset for local runs - bootstrap role has direct S3/DynamoDB access.
  # Set to "arn:aws:iam::135133927908:role/TerragruntDeployRole" in CI/CD.
  terragrunt_deploy_role_arn = ""
  github_actions_role_arn    = "arn:aws:iam::135133927908:role/GitHubActionsDeployRole"
}
