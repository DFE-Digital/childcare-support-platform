output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.id
}

output "cloudfront_distribution_arn" {
  description = "ARN of the CloudFront distribution - feed back into storage module to attach the OAC bucket policy"
  value       = aws_cloudfront_distribution.main.arn
}

output "cloudfront_hosted_zone_id" {
  description = "CloudFront's fixed hosted zone ID — required for Route53 alias records"
  value       = aws_cloudfront_distribution.main.hosted_zone_id
}
