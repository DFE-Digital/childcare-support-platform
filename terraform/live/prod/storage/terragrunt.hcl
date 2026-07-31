include "root" {
  path   = find_in_parent_folders()
  expose = true
}

locals {
  common   = read_terragrunt_config(find_in_parent_folders("common.hcl"))
  env_vars = read_terragrunt_config(find_in_parent_folders("_env/prod.hcl"))
}

# Two-phase deploy for the OAC bucket policy (chicken-and-egg with cdn modules):
#
# Phase 1 - first deploy of a new cdn module:
#   Apply storage with cloudfront_distribution_arns = [] (no bucket policy created).
#   Then apply the cdn module.
#
# Phase 2 - after each cdn module is applied:
#   Add the new distribution ARN to cloudfront_distribution_arns, obtained from:
#   make tg/output env=prod module=<cdn-module>
#   Then re-apply storage to update the OAC bucket policies.
#   A terragrunt dependency block is intentionally omitted here to avoid a
#   cycle: cdn -> storage -> cdn.
#
terraform {
  source = "../../../modules//storage"
}

inputs = {
  project     = local.common.locals.project_name
  environment = local.env_vars.locals.environment

  # List of CloudFront distribution ARNs allowed to read from the S3 buckets.
  # Add a new ARN after each cdn module is applied (make tg/output env=prod module=<cdn>),
  # then re-apply storage.
  cloudfront_distribution_arns = [
    # cdn (bsil.10ds.cabinetoffice.gov.uk)
    "arn:aws:cloudfront::522029197016:distribution/EZIGJKIDYSLF2",
    # cdn-childcare (childcare.beststartinlife.gov.uk)
    "arn:aws:cloudfront::522029197016:distribution/E3OZDH533ZIVMV",
  ]
}
