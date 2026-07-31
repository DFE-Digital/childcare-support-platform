terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

locals {
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terragrunt"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Manual Deployer ("Switch Role" / Jump-User pattern)
#
# Architecture:
#   IAM User  →  Deployment-Users-Group  →  sts:AssumeRole  →  Manual-Deployer-Role
#
# Users have NO direct permissions. All privilege flows through the role, which
# requires MFA to assume. CloudTrail records every AssumeRole call for auditability.
# -----------------------------------------------------------------------------

# --- Manual-Deployer-Role --------------------------------------------------

data "aws_iam_policy_document" "manual_deployer_trust" {
  statement {
    sid     = "AllowAccountWithMFA"
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    # MFA is enforced by the DenyAllWithoutMFA group policy rather than here,
    # because aws-vault calls AssumeRole directly (not via GetSessionToken), so
    # aws:MultiFactorAuthPresent is not set on the resulting session context.
    condition {
      test     = "NumericLessThanEquals"
      variable = "sts:DurationSeconds"
      values   = ["28800"]
    }
  }
}

resource "aws_iam_role" "manual_deployer" {
  name                 = "Manual-Deployer-Role"
  assume_role_policy   = data.aws_iam_policy_document.manual_deployer_trust.json
  max_session_duration = 28800
  tags                 = local.tags
}

# Scoped to the operations the Makefile deploy targets actually perform:
#   bsil/check-account    → sts:GetCallerIdentity
#   cdn/push-provider-data, data/push-exported, frontend/deploy, fetch-data-bsil
#                         → S3 on beststartinlife-<env>-* buckets
#   frontend/deploy       → CloudFront invalidation
#   sis/deploy            → Lambda update-function-code

data "aws_iam_policy_document" "deployer_permissions" {
  # Account identity check used by bsil/check-account
  statement {
    sid       = "CallerIdentity"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }

  # S3 — BSIL buckets in this environment only
  statement {
    sid       = "S3ListAllBuckets"
    effect    = "Allow"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  statement {
    sid    = "S3BucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:ListBucketVersions",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:GetBucketTagging",
    ]
    resources = ["arn:aws:s3:::beststartinlife-${var.environment}-*"]
  }

  statement {
    sid    = "S3ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::beststartinlife-${var.environment}-*/*"]
  }

  # Lambda — spatial index function in this environment only
  statement {
    sid    = "LambdaDeploy"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
    ]
    resources = [
      "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:beststartinlife-${var.environment}-*",
    ]
  }

  # CloudFront — list all distributions (no resource filter available in IAM),
  # invalidate any distribution in this account (frontend/deploy resolves the ID at runtime)
  statement {
    sid       = "CloudFrontList"
    effect    = "Allow"
    actions   = ["cloudfront:ListDistributions"]
    resources = ["*"]
  }

  statement {
    sid    = "CloudFrontInvalidate"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
    ]
    resources = ["arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/*"]
  }
}

resource "aws_iam_role_policy" "deployer_permissions" {
  name   = "DeployerPermissions"
  role   = aws_iam_role.manual_deployer.id
  policy = data.aws_iam_policy_document.deployer_permissions.json
}

# --- Deployment-Users-Group ------------------------------------------------

resource "aws_iam_group" "deployment_users" {
  name = "Deployment-Users-Group"
}

data "aws_iam_policy_document" "group_assume_deployer" {
  statement {
    sid       = "AssumeDeployerRole"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.manual_deployer.arn]

    dynamic "condition" {
      for_each = length(var.allowed_ip_ranges) > 0 ? [1] : []
      content {
        test     = "IpAddress"
        variable = "aws:SourceIp"
        values   = var.allowed_ip_ranges
      }
    }
  }

  statement {
    sid       = "TagSession"
    effect    = "Allow"
    actions   = ["sts:TagSession"]
    resources = ["*"]
  }
}

resource "aws_iam_group_policy" "assume_deployer" {
  name   = "AssumeManualDeployerRole"
  group  = aws_iam_group.deployment_users.name
  policy = data.aws_iam_policy_document.group_assume_deployer.json
}

# Temporary: attach deployer permissions directly to the group while SCP
# investigation is ongoing (sts:AssumeRole blocked at org level).
resource "aws_iam_group_policy" "deployer_permissions_direct" {
  name   = "DeployerPermissionsDirect"
  group  = aws_iam_group.deployment_users.name
  policy = data.aws_iam_policy_document.deployer_permissions.json
}

# BoolIfExists catches both explicit false and absent key (long-term credentials).
# iam:ChangePassword is exempted so users can change a temporary password before
# they have MFA set up.
data "aws_iam_policy_document" "group_mfa_enforce" {
  statement {
    sid    = "DenyAllWithoutMFA"
    effect = "Deny"

    not_actions = [
      "iam:ChangePassword",
      "iam:CreateVirtualMFADevice",
      "iam:EnableMFADevice",
      "iam:GetMFADevice",
      "iam:GetUser",
      "iam:ListMFADevices",
      "iam:ListVirtualMFADevices", # account-scoped; can't restrict to specific resource
      "iam:ResyncMFADevice",
      "sts:AssumeRole",
      "sts:TagSession",
      "sts:GetSessionToken",
    ]

    resources = ["*"]

    condition {
      test     = "BoolIfExists"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["false"]
    }
  }
}

resource "aws_iam_group_policy" "mfa_enforce" {
  name   = "EnforceMFA"
  group  = aws_iam_group.deployment_users.name
  policy = data.aws_iam_policy_document.group_mfa_enforce.json
}

# --- Self-service policy (password change + MFA management) ---------------
# Users need iam:ChangePassword on their own user ARN, and GetAccountPasswordPolicy
# so the console can show them the policy requirements before they submit.
# All other MFA self-service actions are scoped to the caller's own user/device.

data "aws_iam_policy_document" "group_self_service" {
  # Allow users to change their own console password
  statement {
    sid     = "AllowOwnPasswordChange"
    effect  = "Allow"
    actions = ["iam:ChangePassword"]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/$${aws:username}",
    ]
  }

  # Allow users to read the account password policy so the console shows requirements
  statement {
    sid       = "AllowGetPasswordPolicy"
    effect    = "Allow"
    actions   = ["iam:GetAccountPasswordPolicy"]
    resources = ["*"]
  }

  # Allow users to manage their own MFA devices
  statement {
    sid    = "AllowMFASelfManage"
    effect = "Allow"
    actions = [
      "iam:CreateVirtualMFADevice",
      "iam:EnableMFADevice",
      "iam:GetMFADevice",
      "iam:GetUser",
      "iam:ListMFADevices",
      "iam:ResyncMFADevice",
      "iam:DeleteVirtualMFADevice",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/$${aws:username}",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:mfa/$${aws:username}",
    ]
  }

  # ListVirtualMFADevices is account-scoped and cannot be restricted to a specific resource
  statement {
    sid       = "AllowListVirtualMFADevices"
    effect    = "Allow"
    actions   = ["iam:ListVirtualMFADevices"]
    resources = ["*"]
  }

  # Allow users to manage their own access keys
  statement {
    sid    = "AllowAccessKeySelfManage"
    effect = "Allow"
    actions = [
      "iam:CreateAccessKey",
      "iam:DeleteAccessKey",
      "iam:GetAccessKeyLastUsed",
      "iam:ListAccessKeys",
      "iam:ListUserTags",
      "iam:TagUser",
      "iam:UpdateAccessKey",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/$${aws:username}",
    ]
  }

  # Allow getting a session token (needed to call AssumeRole with MFA from the CLI)
  statement {
    sid       = "AllowGetSessionToken"
    effect    = "Allow"
    actions   = ["sts:GetSessionToken"]
    resources = ["*"]
  }
}

resource "aws_iam_group_policy" "self_service" {
  name   = "SelfServicePasswordAndMFA"
  group  = aws_iam_group.deployment_users.name
  policy = data.aws_iam_policy_document.group_self_service.json
}

# --- Deployer users --------------------------------------------------------
# Managed via deploy_users in live/<env>/iam/terragrunt.hcl.
# Adding a name creates the IAM user and adds it to Deployment-Users-Group.
# Removing a name destroys the user and all credentials (force_destroy = true).

resource "aws_iam_user" "deployers" {
  for_each = var.deploy_users

  name          = each.key
  force_destroy = true
  tags          = local.tags
}

resource "aws_iam_user_group_membership" "deployers" {
  for_each = var.deploy_users

  user   = aws_iam_user.deployers[each.key].name
  groups = [aws_iam_group.deployment_users.name]
}
