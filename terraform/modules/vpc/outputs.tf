output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets, or empty list if not created"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the three private subnets"
  value       = aws_subnet.private[*].id
}

output "nat_gateway_id" {
  description = "ID of the NAT Gateway, or null if not created"
  value       = var.create_nat_gateway ? aws_nat_gateway.main[0].id : null
}

output "s3_endpoint_id" {
  description = "ID of the S3 Gateway VPC endpoint, or null if not created"
  value       = var.create_nat_gateway ? aws_vpc_endpoint.s3[0].id : null
}
