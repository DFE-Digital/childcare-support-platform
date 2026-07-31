variable "project" {
  description = "Project name, used in resource names and tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID in which to create the security groups"
  type        = string
}
