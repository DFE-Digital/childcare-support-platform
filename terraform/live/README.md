# Terragrunt Live Layer

Environment-specific Terragrunt configurations that wire the [modules](../modules/) together for `dev`, `preprod`, and `prod`.

## Directory structure

```
live/
├── terragrunt.hcl          # Root config - remote state backend, provider generation
├── common.hcl              # Shared locals (project_name, aws_region)
├── common.tfvars           # Shared inputs passed to all modules
├── _env/
│   ├── dev.hcl             # Dev environment locals (CIDRs, runner type, etc.)
│   ├── preprod.hcl         # Preprod environment locals
│   └── prod.hcl            # Prod environment locals
├── dev/
│   ├── env.tfvars          # Dev account values (populate from bootstrap outputs)
│   ├── vpc/terragrunt.hcl
│   ├── security/terragrunt.hcl
│   ├── storage/terragrunt.hcl
│   ├── compute/terragrunt.hcl
│   └── cdn/terragrunt.hcl
├── preprod/                # Same structure as dev/
└── prod/                   # Same structure as dev/
```

## Configuration layers

| File | Purpose | Updated by |
|---|---|---|
| `terragrunt.hcl` | S3 backend, DynamoDB lock, provider | One-off setup |
| `common.hcl` | `project_name`, `aws_region` locals | Rarely |
| `common.tfvars` | Shared `inputs` map for all modules | Rarely |
| `_env/{env}.hcl` | Per-environment variables (CIDRs, instance types) | As needed |
| `{env}/env.tfvars` | Per-account values from bootstrap outputs | After bootstrap |

## Module apply order

The dependency graph determines the required apply order. On first deploy, follow this sequence:

```
1. iam           - no dependencies (human deployer role and users)
2. vpc           - no dependencies
3. security      - needs: vpc.vpc_id
4. storage       - no module dependencies (apply with cloudfront_distribution_arns = [])
5. compute       - needs: vpc.private_subnet_ids, security.lambda_sg_id, security.runner_sg_id, security.waf_regional_arn
6. cdn           - needs: storage.vite_bucket_id, storage.oac_id, security.waf_cloudfront_arn
7. dns-childcare - (prod only) Route53 hosted zone + ACM cert for childcare.beststartinlife.gov.uk
8. cdn-childcare - (prod only) needs: storage, security, dns-childcare, compute
9. storage       - re-apply with cloudfront_distribution_arns = [cdn ARN, cdn-childcare ARN]
```

For each additional cdn module, add its ARN to `cloudfront_distribution_arns` in `storage/terragrunt.hcl` and re-apply storage.

On subsequent deploys, `terragrunt run-all apply` from any env directory resolves the dependency graph automatically (after step 6 is wired up in the storage terragrunt.hcl).

## Running a full environment deploy

All commands are run from the **repo root**. Set your AWS profile first:

```bash
export AWS_PROFILE=bsil-dev   # or bsil-nonprd / bsil-prod
```

Target individual modules:

```bash
make tg/plan env=dev module=vpc
make tg/apply env=dev module=vpc
```

Or deploy all modules in dependency order:

```bash
make tg/plan env=dev module=all
make tg/apply env=dev module=all
```

## Environment CIDRs

Each environment uses a distinct VPC CIDR to allow future peering without overlap:

| Environment | VPC CIDR | Public subnets | Private subnets |
|---|---|---|---|
| dev | `10.0.0.0/16` | `10.0.1-3.0/24` | `10.0.11-13.0/24` |
| preprod | `10.1.0.0/16` | `10.1.1-3.0/24` | `10.1.11-13.0/24` |
| prod | `10.2.0.0/16` | `10.2.1-3.0/24` | `10.2.11-13.0/24` |

## Populating env.tfvars

After running `make bootstrap/apply account=<env>`, copy the outputs into the matching `{env}/env.tfvars`:

```bash
make bootstrap/output account=dev
```

Then fill in [dev/env.tfvars](dev/env.tfvars):

```hcl
inputs = {
  aws_account_id             = "<account_id>"
  tfstate_bucket             = "<tfstate_bucket>"
  tfstate_lock_table         = "<tfstate_lock_table>"
  terragrunt_deploy_role_arn = "<terragrunt_deploy_role_arn>"
  github_actions_role_arn    = "<github_actions_role_arn>"
}
```

## Basic auth (beta protection)

The dev CDN distribution is protected by HTTP basic auth via Lambda@Edge. Credentials are stored as SSM SecureStrings in `us-east-1` and read at Lambda cold start — they are never written to Terraform state or Lambda configuration.

Before applying the `cdn` module for the first time, create the parameters manually in the AWS console (**region must be `us-east-1`**):

| Parameter | Type | Value |
|---|---|---|
| `/beststartinlife/dev/basic-auth/user` | SecureString | your chosen username |
| `/beststartinlife/dev/basic-auth/pass` | SecureString | your chosen password |

Then apply:

```bash
make tg/apply env=dev module=cdn
```

To rotate credentials, update the SSM parameters in the console and redeploy the Lambda (a `tg/apply` on the cdn module is sufficient — CloudFront will pick up the new version).

To disable basic auth for an environment, set `basic_auth_enabled = false` in `{env}/cdn/terragrunt.hcl` and re-apply.

## Runner PAT token

The GitHub Actions runner PAT is never stored in any `.hcl` or `.tfvars` file. Supply it at apply time:

```bash
export TF_VAR_runner_pat_token="ghp_..."
terragrunt apply   # from live/{env}/compute/
```

In CI, set `RUNNER_PAT` as a GitHub Actions secret and pass it as `TF_VAR_runner_pat_token`.

## Module READMEs

- [vpc](../modules/vpc/README.md)
- [security](../modules/security/README.md)
- [storage](../modules/storage/README.md)
- [compute](../modules/compute/README.md)
- [cdn](../modules/cdn/README.md)
