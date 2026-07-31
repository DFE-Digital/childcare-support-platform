variable "project" {
  description = "Project name, used in bucket names and tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "cloudfront_distribution_arns" {
  description = <<-EOT
    ARNs of all CloudFront distributions allowed to read from the S3 buckets.
    Leave empty on first apply (before any cdn module is applied). Re-apply after each
    cdn module is deployed to attach / update the OAC bucket policies.
  EOT
  type        = list(string)
  default     = []
}
