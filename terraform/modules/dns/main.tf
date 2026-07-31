terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
      # us_east_1 alias is required for ACM — CloudFront only accepts us-east-1 certificates.
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
# Route53 Hosted Zone
# -----------------------------------------------------------------------------

resource "aws_route53_zone" "main" {
  name = var.domain_name
  tags = local.tags
}

# -----------------------------------------------------------------------------
# ACM Certificate (must be in us-east-1 for CloudFront)
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "main" {
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = local.tags
}

# DNS validation records in the hosted zone
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.main.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "main" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}
