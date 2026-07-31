locals {
  environment          = "prod"
  aws_region           = "eu-west-2"
  vpc_cidr             = "10.2.0.0/16"
  public_subnet_cidrs  = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
  private_subnet_cidrs = ["10.2.11.0/24", "10.2.12.0/24", "10.2.13.0/24"]
  runner_instance_type = "t3.small"
  github_org           = "PMO-Data-Science"
  github_repo          = "10ds-atlas-beststartinlife"
  create_nat_gateway   = false
}
