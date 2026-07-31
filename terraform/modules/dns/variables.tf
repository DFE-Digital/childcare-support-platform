variable "project" {
  description = "Project name, used in tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "domain_name" {
  description = "The fully-qualified domain name for the hosted zone and certificate (e.g. bsil.10ds.cabinetoffice.gov.uk)"
  type        = string
}
