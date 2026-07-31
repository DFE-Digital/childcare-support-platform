output "waf_cloudfront_arn" {
  description = "ARN of the us-east-1 WAFv2 WebACL for CloudFront"
  value       = aws_wafv2_web_acl.cloudfront.arn
}

output "waf_regional_arn" {
  description = "ARN of the eu-west-2 regional WAFv2 WebACL for API Gateway"
  value       = aws_wafv2_web_acl.regional.arn
}

output "lambda_sg_id" {
  description = "ID of the Lambda security group"
  value       = aws_security_group.lambda.id
}

output "runner_sg_id" {
  description = "ID of the GitHub runner EC2 security group"
  value       = aws_security_group.runner.id
}
