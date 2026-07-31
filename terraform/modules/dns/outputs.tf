output "zone_id" {
  description = "Route53 hosted zone ID"
  value       = aws_route53_zone.main.zone_id
}

output "name_servers" {
  description = "NS records to delegate from the parent zone in your main account"
  value       = aws_route53_zone.main.name_servers
}

output "certificate_arn" {
  description = "ACM certificate ARN (us-east-1) — pass to CloudFront distribution"
  value       = aws_acm_certificate_validation.main.certificate_arn
}
