variable "project" {
  description = "Project name — applied as a tag to all resources"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "deploy_users" {
  description = "Set of IAM usernames to create and add to Deployment-Users-Group. Add/remove names in live/<env>/iam/terragrunt.hcl and re-apply."
  type        = set(string)
  default     = []
}

variable "allowed_ip_ranges" {
  description = "CIDR ranges from which deployers are permitted to call sts:AssumeRole. Restricts the group AssumeRole policy to known office/VPN IPs."
  type        = list(string)
  default     = []
}
