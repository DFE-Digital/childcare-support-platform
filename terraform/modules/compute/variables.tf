variable "project" {
  description = "Project name, used in resource names and tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda and EC2 runner placement"
  type        = list(string)
}

variable "lambda_sg_id" {
  description = "Security group ID for Lambda (from security module)"
  type        = string
}

variable "runner_sg_id" {
  description = "Security group ID for GitHub runner EC2 (from security module)"
  type        = string
}

variable "waf_regional_arn" {
  description = "ARN of the regional WAFv2 WebACL to associate with API Gateway"
  type        = string
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}

variable "lambda_runtime" {
  description = "Lambda runtime identifier"
  type        = string
  default     = "provided.al2023"
}

variable "runner_instance_type" {
  description = "EC2 instance type for the GitHub Actions runner"
  type        = string
  default     = "t3.small"
}

variable "runner_pat_token" {
  description = "GitHub Personal Access Token used to register the Actions runner. Supply via TF_VAR_runner_pat_token - never hardcode. Leave empty to skip runner deployment."
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_org" {
  description = "GitHub organisation name"
  type        = string
  default     = "PMO-Data-Science"
}

variable "github_repo" {
  description = "GitHub repository name (without org prefix)"
  type        = string
}
