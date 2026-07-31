locals {
  buckets = {
    provider_data = "${var.project}-${var.environment}-provider-data"
    vite_outputs  = "${var.project}-${var.environment}-vite-build-outputs"
    source_data   = "${var.project}-${var.environment}-source-data"
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# S3 Buckets - private, versioned, SSE-S3 encrypted
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "this" {
  for_each = local.buckets

  bucket = each.value

  tags = merge(local.tags, { Name = each.value })
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# CloudFront Origin Access Controls
# -----------------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "vite" {
  name                              = "${var.project}-${var.environment}-vite-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_origin_access_control" "provider_data" {
  name                              = "${var.project}-${var.environment}-provider-data-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# -----------------------------------------------------------------------------
# vite-build-outputs bucket policy
#
# Base deny statements are unconditional — enforced from first deploy.
# The OAC Allow is added in a second document once CloudFront ARNs are known,
# then merged via source_policy_documents into a single bucket policy.
#
# Two-phase deploy:
#   Phase 1 (before cdn): cloudfront_distribution_arns = [] — only Deny statements applied.
#   Phase 2 (after cdn):  set cloudfront_distribution_arns and re-apply storage.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "vite_base" {
  statement {
    sid    = "DenyNonHTTPS"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this["vite_outputs"].arn,
      "${aws_s3_bucket.this["vite_outputs"].arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

}

data "aws_iam_policy_document" "vite_oac_allow" {
  count = length(var.cloudfront_distribution_arns) > 0 ? 1 : 0

  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.this["vite_outputs"].arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = var.cloudfront_distribution_arns
    }
  }
}

data "aws_iam_policy_document" "vite_final" {
  source_policy_documents = concat(
    [data.aws_iam_policy_document.vite_base.json],
    length(var.cloudfront_distribution_arns) > 0 ? [data.aws_iam_policy_document.vite_oac_allow[0].json] : [],
  )
}

resource "aws_s3_bucket_policy" "vite" {
  bucket = aws_s3_bucket.this["vite_outputs"].id
  policy = data.aws_iam_policy_document.vite_final.json

  depends_on = [aws_s3_bucket_public_access_block.this["vite_outputs"]]
}

# -----------------------------------------------------------------------------
# provider-data bucket policy  (same two-phase pattern as vite above)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "provider_data_base" {
  statement {
    sid    = "DenyNonHTTPS"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this["provider_data"].arn,
      "${aws_s3_bucket.this["provider_data"].arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

}

data "aws_iam_policy_document" "provider_data_oac_allow" {
  count = length(var.cloudfront_distribution_arns) > 0 ? 1 : 0

  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.this["provider_data"].arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = var.cloudfront_distribution_arns
    }
  }
}

data "aws_iam_policy_document" "provider_data_final" {
  source_policy_documents = concat(
    [data.aws_iam_policy_document.provider_data_base.json],
    length(var.cloudfront_distribution_arns) > 0 ? [data.aws_iam_policy_document.provider_data_oac_allow[0].json] : [],
  )
}

resource "aws_s3_bucket_policy" "provider_data" {
  bucket = aws_s3_bucket.this["provider_data"].id
  policy = data.aws_iam_policy_document.provider_data_final.json

  depends_on = [aws_s3_bucket_public_access_block.this["provider_data"]]
}

# -----------------------------------------------------------------------------
# source-data bucket policy
# No CloudFront origin — accessed only by deployers and GitHub Actions runners.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "source_data" {
  statement {
    sid    = "DenyNonHTTPS"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this["source_data"].arn,
      "${aws_s3_bucket.this["source_data"].arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyCrossAccount"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this["source_data"].arn,
      "${aws_s3_bucket.this["source_data"].arn}/*",
    ]

    condition {
      test     = "StringNotEquals"
      variable = "aws:PrincipalAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_s3_bucket_policy" "source_data" {
  bucket = aws_s3_bucket.this["source_data"].id
  policy = data.aws_iam_policy_document.source_data.json

  depends_on = [aws_s3_bucket_public_access_block.this["source_data"]]
}

# -----------------------------------------------------------------------------
# Moved blocks — rename bucket policy resources from the conditional count-based
# pattern to unconditional singletons. Prevents destroy+create on apply.
# -----------------------------------------------------------------------------

moved {
  from = aws_s3_bucket_policy.vite_oac[0]
  to   = aws_s3_bucket_policy.vite
}

moved {
  from = aws_s3_bucket_policy.provider_data_oac[0]
  to   = aws_s3_bucket_policy.provider_data
}
