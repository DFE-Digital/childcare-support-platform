output "manual_deployer_role_arn" {
  description = "ARN of the Manual-Deployer-Role"
  value       = aws_iam_role.manual_deployer.arn
}

