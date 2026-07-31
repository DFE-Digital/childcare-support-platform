include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/prod.hcl"))
}

terraform {
  source = "../../../modules//iam"
}

inputs = {
  project     = local.common.locals.project_name
  environment = local.env_vars.locals.environment

  # Human deployers with Switch Role access to this account.
  # Add/remove names here and run: make tg/apply env=prod module=iam
  deploy_users = [
    "joe.early@cabinetoffice.gov.uk",
    "christopher.hinds@cabinetoffice.gov.uk",
    "john.higgins1@cabinetoffice.gov.uk",
  ]

  allowed_ip_ranges = [
    "217.196.229.77/32",
    "217.196.229.79/32",
    "217.196.229.80/32",
    "217.196.229.81/32",
    "51.149.8.0/25",
    "51.149.8.128/29",
    "3.9.56.99/32",
  ]
}
