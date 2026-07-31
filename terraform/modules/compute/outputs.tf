output "lambda_function_arn" {
  description = "ARN of the spatial index Lambda function"
  value       = aws_lambda_function.main.arn
}

output "lambda_function_name" {
  description = "Name of the spatial index Lambda function"
  value       = aws_lambda_function.main.function_name
}

output "api_gateway_url" {
  description = "Invoke URL of the API Gateway stage"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.eu-west-2.amazonaws.com/${var.environment}"
}

output "api_gateway_id" {
  description = "ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_key_id" {
  description = "API Gateway key ID - retrieve the value with: aws apigateway get-api-key --api-key <id> --include-value"
  value       = aws_api_gateway_api_key.main.id
}

output "api_key_ssm_param" {
  description = "SSM parameter path where the API Gateway key value is stored (read by CDN module to inject into CloudFront Function)"
  value       = aws_ssm_parameter.api_key.name
}

output "runner_instance_id" {
  description = "EC2 instance ID of the GitHub Actions runner (empty if runner not deployed)"
  value       = local.deploy_runner == 1 ? aws_instance.runner[0].id : null
  sensitive   = true
}
