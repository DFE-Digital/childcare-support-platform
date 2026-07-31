terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
      # The us_east_1 alias must be passed in by the caller.
      # WAFv2 CLOUDFRONT scope is a hard AWS requirement to reside in us-east-1.
      configuration_aliases = [aws.us_east_1]
    }
  }
}

locals {
  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# -----------------------------------------------------------------------------
# WAF - CloudFront (GLOBAL, must be us-east-1)
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "cloudfront" {
  provider = aws.us_east_1

  name  = "${var.project}-${var.environment}-cloudfront-waf"
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-cloudfront-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-${var.environment}-cloudfront-waf"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# WAF - API Gateway (REGIONAL, eu-west-2)
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "regional" {
  name  = "${var.project}-${var.environment}-regional-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-regional-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-${var.environment}-regional-waf"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Security Groups - egress-only (no public ingress)
# -----------------------------------------------------------------------------

resource "aws_security_group" "lambda" {
  name        = "${var.project}-${var.environment}-lambda-sg"
  description = "Lambda function - egress to 443 only, no ingress"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS egress to AWS APIs and internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-lambda-sg" })
}

resource "aws_security_group" "runner" {
  name        = "${var.project}-${var.environment}-runner-sg"
  description = "GitHub Actions runner EC2 - egress to 443 only, no ingress"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS egress to GitHub and AWS APIs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-runner-sg" })
}
