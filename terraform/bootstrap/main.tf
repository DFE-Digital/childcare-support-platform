# -----------------------------------------------------------------------------
# Bootstrap - run once per account using the bootstrap IAM role
# Creates the prerequisites that Terragrunt/Terraform depends on:
#   - S3 state bucket
#   - DynamoDB lock table
#   - GitHub Actions OIDC provider + deployment role
#
# Human deployer access (Manual-Deployer-Role, users, group) is managed
# separately via the live/iam Terragrunt module once bootstrap has run.
#
# Usage (from repo root):
#   export AWS_PROFILE=<bootstrap-profile>
#   make bootstrap/plan  account=dev
#   make bootstrap/apply account=dev
#   make bootstrap/output account=dev   # outputs include the Switch Role console URL
#
# Available accounts: dev, preprod, prod (maps to bootstrap/accounts/<account>.tfvars)
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bootstrap state is stored locally - it manages its own remote state bucket,
  # so it cannot itself use remote state. Commit the generated .tfstate carefully
  # or migrate it manually after first apply.
  backend "local" {}
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "account_name" {
  description = "Short name for this account (e.g. dev, prod, shared). Used in resource names."
  type        = string
}

variable "project" {
  description = "Project tag applied to all resources"
  type        = string
  default     = "beststartinlife"
}

variable "github_org" {
  description = "GitHub organisation name"
  type        = string
  default     = "PMO-Data-Science"
}

variable "github_repo" {
  description = "GitHub repository name (without org prefix)"
  type        = string
  default     = "10ds-atlas-beststartinlife"
}

# -----------------------------------------------------------------------------
# S3 - Terraform state bucket
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "tfstate" {
  bucket = "bsil-${var.account_name}-tfstate"

  tags = {
    Project     = var.project
    Environment = var.account_name
    ManagedBy   = "terraform-bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# DynamoDB - state lock table
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "tfstate_lock" {
  name         = "bsil-${var.account_name}-tfstate-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project     = var.project
    Environment = var.account_name
    ManagedBy   = "terraform-bootstrap"
  }
}

# -----------------------------------------------------------------------------
# IAM - GitHub Actions OIDC
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC thumbprint (stable - see https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8518e8759bf075b76b750d4f2df264fcd"]
}

data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # main branch, tags, and workflow_dispatch (which can run from any branch)
      values = [
        "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main",
        "repo:${var.github_org}/${var.github_repo}:ref:refs/tags/*",
        "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/*",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "GitHubActionsDeployRole"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json

  tags = {
    Project     = var.project
    Environment = var.account_name
    ManagedBy   = "terraform-bootstrap"
  }
}

# Attach AdministratorAccess for now - scope this down once you know
# exactly which services are needed.
resource "aws_iam_role_policy_attachment" "github_actions_admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# -----------------------------------------------------------------------------
# IAM - Terragrunt deploy role (assumed by GitHub Actions or humans)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "terragrunt_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type = "AWS"
      identifiers = [
        aws_iam_role.github_actions.arn,
        # Bootstrap role - allows local Terragrunt runs using the bootstrap profile
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/bootstrap",
        # Add SSO role ARNs here for developer access
        # "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/YourSSORole",
      ]
    }
  }
}

resource "aws_iam_role" "terragrunt_deploy" {
  name               = "TerragruntDeployRole"
  assume_role_policy = data.aws_iam_policy_document.terragrunt_assume.json

  tags = {
    Project     = var.project
    Environment = var.account_name
    ManagedBy   = "terraform-bootstrap"
  }
}

resource "aws_iam_role_policy_attachment" "terragrunt_deploy_admin" {
  role       = aws_iam_role.terragrunt_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# -----------------------------------------------------------------------------
# Outputs - paste these into live/<env>/env.tfvars after bootstrap
# -----------------------------------------------------------------------------

output "tfstate_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}

output "tfstate_lock_table" {
  value = aws_dynamodb_table.tfstate_lock.name
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "terragrunt_deploy_role_arn" {
  value = aws_iam_role.terragrunt_deploy.arn
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

