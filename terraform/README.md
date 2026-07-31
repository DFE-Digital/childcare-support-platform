# Terraform

This directory contains three layers of infrastructure:

| Directory | Purpose | README |
|---|---|---|
| `bootstrap/` | One-time account setup - S3 state bucket, DynamoDB lock table, GitHub Actions OIDC role | - |
| `modules/` | Reusable Terraform modules (vpc, security, storage, compute, cdn) | [modules/README.md](modules/README.md) |
| `live/` | Terragrunt environment configs wiring modules together for dev/preprod/prod | [live/README.md](live/README.md) |

## Module quick-reference

| Module | What it builds |
|---|---|
| [vpc](modules/vpc/README.md) | VPC, 3×public + 3×private subnets, IGW, NAT Gateway, S3 endpoint |
| [security](modules/security/README.md) | WAFv2 WebACLs (CloudFront global + API Gateway regional), egress-only security groups |
| [storage](modules/storage/README.md) | S3 buckets (provider-data, vite-build-outputs), CloudFront OACs for both |
| [compute](modules/compute/README.md) | Lambda (spatial index), API Gateway REST, EC2 GitHub Actions runner |
| [cdn](modules/cdn/README.md) | CloudFront distribution — vite-build-outputs (default `/`) + provider-data (`/data/*`), WAF, SPA error handling |

---

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6.0 (tested on 1.14.7)
- [Terragrunt](https://terragrunt.gruntwork.io/docs/getting-started/install/) >= 0.50 (tested on 0.99.4)
- AWS CLI configured with SSO (`aws sso login --profile <profile>`)
- Sufficient IAM permissions in the target account (see below)

> **Note:** Terraform >= 1.6 changed the S3 backend - `role_arn` must now be nested inside an `assume_role {}` block. The root `terragrunt.hcl` handles this automatically.

---

## 1. Bootstrap (run once per account)

Bootstrap creates the prerequisites that all subsequent Terraform runs depend on. It uses a **local** state backend - the generated `.tfstate` file should be committed or migrated manually after the first apply.

### What it creates

- `bsil-<account>-tfstate` - S3 bucket for Terraform remote state
- `bsil-<account>-tfstate-lock` - DynamoDB table for state locking
- `GitHubActionsDeployRole` - IAM role assumed by GitHub Actions via OIDC
- `TerragruntDeployRole` - IAM role assumed for Terraform applies

### Required IAM permissions

Bootstrap must be run with a role that can create S3 buckets, DynamoDB tables, and IAM roles/policies. Use your account's bootstrap or admin role:

```bash
export AWS_PROFILE=bsil-dev   # or bsil-nonprd / bsil-prod
```

### Running bootstrap

Use the Makefile targets from the repo root. The `account` argument maps to a tfvars file under `bootstrap/accounts/`:

```bash
# Plan changes
make bootstrap/plan account=dev

# Apply
make bootstrap/apply account=dev

# Review outputs
make bootstrap/output account=dev
```

Available accounts: `dev`, `preprod`, `prod`.

### After bootstrap - populate env.tfvars

Once bootstrap has applied, copy the outputs into the matching `live/<env>/env.tfvars`:

```bash
make bootstrap/output account=dev
```

Paste the values into [live/dev/env.tfvars](live/dev/env.tfvars):

```hcl
inputs = {
  aws_account_id             = "<output: account_id>"
  tfstate_bucket             = "<output: tfstate_bucket>"
  tfstate_lock_table         = "<output: tfstate_lock_table>"
  github_actions_role_arn    = "<output: github_actions_role_arn>"

  # Leave empty for local runs - the bootstrap role accesses state directly.
  # Set to the TerragruntDeployRole ARN in CI/CD only.
  terragrunt_deploy_role_arn = ""
}
```

Repeat for `preprod` and `prod` when bootstrapping those accounts.

### Manual deployer access (Switch Role)

Human deployers use the Jump-User pattern: IAM users hold no direct permissions and must assume `Manual-Deployer-Role` via MFA to do anything privileged.

This is managed by the `iam` Terragrunt module, applied **after** bootstrap (it uses the remote S3 state backend that bootstrap creates):

```bash
make tg/apply env=dev module=iam
```

**Adding a new deployer**

Add the username to `deploy_users` in `terraform/live/<env>/iam/terragrunt.hcl` and re-apply:

```bash
make tg/apply env=dev module=iam
```

Sessions last up to 8 hours. The role is scoped to the operations the Makefile deploy targets need: S3 read/write on `beststartinlife-<env>-*` buckets, `lambda:UpdateFunctionCode` on the spatial index function, and CloudFront invalidations.

See [docs/DEPLOYER_ACCESS.md](../docs/DEPLOYER_ACCESS.md) for the full new-user onboarding and aws-vault setup guide.

---

## 2. Live infrastructure (day-to-day deploys)

The `live/` layer uses Terragrunt to manage per-environment state and variable inheritance. Each environment directory (`dev/`, `preprod/`, `prod/`) inherits from the root [live/terragrunt.hcl](live/terragrunt.hcl) and merges its own `env.tfvars`.

### Directory layout

```
live/
├── terragrunt.hcl          # Root config - remote state, provider generation
├── common.hcl              # Shared locals (project_name, aws_region)
├── common.tfvars           # Shared inputs (project, region, GitHub org/repo)
├── _env/
│   ├── dev.hcl             # Dev locals (CIDRs, instance types)
│   ├── preprod.hcl
│   └── prod.hcl
├── dev/
│   ├── env.tfvars          # Dev account values (from bootstrap outputs)
│   ├── vpc/terragrunt.hcl
│   ├── security/terragrunt.hcl
│   ├── storage/terragrunt.hcl
│   ├── compute/terragrunt.hcl
│   └── cdn/terragrunt.hcl
├── preprod/                # Same structure as dev/
└── prod/                   # Same structure as dev/
```

See [live/README.md](live/README.md) for the full apply order and dependency graph.

### Deploying via Makefile

Application deploys are handled by CI (GitHub Actions), but you can run them locally using the existing `tf/` targets with `instance=live/<env>`:

```bash
# Plan
make tf/plan instance=live/dev env=default

# Apply
make tf/apply instance=live/dev env=default
```

> The `image_tag` variable defaults to the current git SHA (`git rev-parse HEAD`). Pass `args='-var image_tag=<tag>'` to override.

### CI/CD (GitHub Actions)

Deployments to `preprod` and `prod` are triggered automatically on merge to `main`. The workflow assumes `GitHubActionsDeployRole` via OIDC - no long-lived credentials are stored.

To trigger a deployment manually:

```bash
gh workflow run deploy.yml -f environment=dev
```

---

## 3. First-time deployment steps

### Step 1 - Bootstrap each account

Run once per account (`dev`, `preprod`, `prod`):

```bash
export AWS_PROFILE=<bootstrap-profile-for-dev>
make bootstrap/apply account=dev
make bootstrap/output account=dev
```

Paste the outputs into [live/dev/env.tfvars](live/dev/env.tfvars) (see section 1 above). Repeat for `preprod` and `prod`.

Commit the populated files:

```bash
git add terraform/live/dev/env.tfvars terraform/live/preprod/env.tfvars terraform/live/prod/env.tfvars
git commit -m "chore(infra): populate env.tfvars from bootstrap outputs"
```

> These files contain account IDs and role ARNs - no secrets - but review before committing.

### Step 2 - Deploy modules in order

All Terragrunt commands are run from the **repo root** via the Makefile. Set your AWS profile first:

```bash
export AWS_PROFILE=bsil-dev
```

Starting with `dev` (promote to `preprod` and `prod` once validated):

```bash
# 1. Network
make tg/apply env=dev module=vpc

# 2. WAF + security groups (requires vpc to exist)
make tg/apply env=dev module=security

# 3. S3 buckets + OAC (no CDN ARN yet - see two-pass note below)
make tg/apply env=dev module=storage

# 4. Lambda + API Gateway + runner (requires vpc + security)
export TF_VAR_runner_pat_token="ghp_..."
make tg/apply env=dev module=compute

# 5. CloudFront (requires storage.oac_id + security.waf_cloudfront_arn)
make tg/apply env=dev module=cdn
```

### Step 3 - Wire up the OAC bucket policies (two-pass)

The CloudFront distribution ARN must be fed back into the storage module to lock down S3 access on **both** the vite-build-outputs and provider-data buckets:

```bash
# Get the distribution ARN
make tg/output env=dev module=cdn

# In terraform/live/dev/storage/terragrunt.hcl:
#   Add the ARN to the cloudfront_distribution_arns list

make tg/apply env=dev module=storage
```

For prod, which has two distributions (`cdn` and `cdn-childcare`), both ARNs must be in the list:

```hcl
cloudfront_distribution_arns = [
  "arn:aws:cloudfront::<account>:distribution/<cdn-id>",
  "arn:aws:cloudfront::<account>:distribution/<cdn-childcare-id>",
]
```

See [storage module README](modules/storage/README.md#two-pass-deployment) for details.

### Step 4 - Add GitHub Actions secrets

In GitHub repo settings (Settings → Secrets → Actions):

| Secret | Value |
|---|---|
| `RUNNER_PAT` | GitHub PAT with `repo` scope - used as `TF_VAR_runner_pat_token` |
| `AWS_ROLE_ARN_DEV` | `github_actions_role_arn` from dev bootstrap output |
| `AWS_ROLE_ARN_PREPROD` | `github_actions_role_arn` from preprod bootstrap output |
| `AWS_ROLE_ARN_PROD` | `github_actions_role_arn` from prod bootstrap output |

### Step 5 - Deploy the application

```bash
# Frontend - sync Vite build to S3 (CloudFront serves from here)
aws s3 sync dist/ s3://beststartinlife-dev-vite-build-outputs/

# Backend - replace Lambda placeholder with real code
aws lambda update-function-code \
  --function-name beststartinlife-dev-spatial-index \
  --zip-file fileb://your-function.zip
```

Verify using the Terraform outputs:

```bash
terragrunt output --terragrunt-working-dir cdn   # cloudfront_domain
terragrunt output --terragrunt-working-dir compute  # api_gateway_url
```

### Subsequent deploys

After the first deploy, `run-all` resolves the dependency graph automatically:

```bash
start-bsil-dev                    # authenticate via aws-vault
make tg/plan env=dev module=all
make tg/apply env=dev module=all
```

---

## 4. Day-to-day operations

### Deploying updated provider data

After running the data pipeline locally:

```bash
make data/export-app BETA=true METADATA=false  # export published data to exported_data/app/
make data/push-exported env=dev                # upload to source-data bucket
```

Then trigger the deploy GitHub Action, which syncs from the source-data bucket to the live provider-data bucket and invalidates CloudFront.

### Deploying the frontend

```bash
start-bsil-dev
make frontend/deploy env=dev      # builds Vite SPA, syncs to vite-build-outputs, invalidates CloudFront
```

### Deploying the Lambda (spatial index service)

The Lambda is deployed via the `sis/lambda-bundle` Make target which packages the Rust binary with the `.sis` index file:

```bash
make data/export-app              # ensures spatial_index.parquet is in exported_data/app/
make sis/lambda-bundle            # compiles Rust + bundles with spatial_index.sis → packages/spatial-index-service/target/sis-lambda.zip

start-bsil-dev
aws lambda update-function-code \
  --function-name beststartinlife-dev-spatial-index \
  --zip-file fileb://packages/spatial-index-service/target/sis-lambda.zip
```

Set these environment variables on the Lambda function:

| Variable | Value |
|---|---|
| `SIS_API_TYPE` | `lambda` |
| `SIS_FILEPATH` | `spatial_index.sis` |
| `SIS_SCHEMA_JSON_PATH` | `sis_schema.json` |

### Known gotchas

| Issue | Fix |
|---|---|
| `role_arn is not expected here` | Terraform >= 1.6 requires `role_arn` inside `assume_role {}` - already handled in `terragrunt.hcl` |
| `Cannot assume IAM Role` (403) | `terragrunt_deploy_role_arn` is set for a local run - set it to `""` in `env.tfvars` for local use |
| `Reference to undeclared input variable` in `provider.tf` | Old cached `provider.tf` using `var.aws_region` - delete `.terragrunt-cache/` and re-run |
| Stale state lock after failed run | Delete the lock entry from DynamoDB: `aws dynamodb delete-item --table-name bsil-<env>-tfstate-lock --key '{"LockID": {"S": "bsil-<env>-tfstate/beststartinlife/<env>/<module>/terraform.tfstate"}}'` |
| State checksum mismatch after lock removal | Update the DynamoDB digest: `aws dynamodb put-item --table-name bsil-<env>-tfstate-lock --item '{"LockID": {"S": "bsil-<env>-tfstate/beststartinlife/<env>/<module>/terraform.tfstate-md5"}, "Digest": {"S": "<calculated-checksum>"}}'` (checksum shown in error output) |
| `env.tfvars` has empty strings | Bootstrap not run yet, or outputs not pasted in |
| `runner_pat_token` variable not set | `export TF_VAR_runner_pat_token=...` before applying `compute` |
| CloudFront returns 403 after first deploy | Expected — complete the two-pass OAC step (Step 3). For prod, ensure all distribution ARNs are in the `cloudfront_distribution_arns` list in `storage/terragrunt.hcl`. |
| WAF plan fails with provider error | Check `security/terragrunt.hcl` generated the `us_east_1` provider alias |
| Runner doesn't register with GitHub | SSM into the instance and check `journalctl -u actions.runner.*` |

---

## Destroying resources

For live infrastructure, use the GitHub Actions workflow rather than running destroy locally:

```bash
make delete-terraform env=dev
```

To tear down bootstrap resources (e.g. decommissioning an account):

```bash
make bootstrap/destroy account=dev
```

> This will prompt for confirmation before proceeding.
