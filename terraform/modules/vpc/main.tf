locals {
  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-vpc" })
}

resource "aws_subnet" "public" {
  count = var.create_nat_gateway ? 3 : 0

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-public-${count.index + 1}" })
}

resource "aws_subnet" "private" {
  count = 3

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-private-${count.index + 1}" })
}

resource "aws_internet_gateway" "main" {
  count = var.create_nat_gateway ? 1 : 0

  vpc_id = aws_vpc.main.id

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-igw" })
}

resource "aws_eip" "nat" {
  count = var.create_nat_gateway ? 1 : 0

  domain = "vpc"

  depends_on = [aws_internet_gateway.main]

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-nat-eip" })
}

# Single NAT Gateway in the first public subnet.
# Cost-saving trade-off: all private subnets share one NAT Gateway.
# For prod, consider a NAT Gateway per AZ for HA.
resource "aws_nat_gateway" "main" {
  count = var.create_nat_gateway ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  depends_on = [aws_internet_gateway.main]

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-nat" })
}

resource "aws_route_table" "public" {
  count = var.create_nat_gateway ? 1 : 0

  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count = var.create_nat_gateway ? 3 : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-private-rt" })
}

resource "aws_route" "private_nat" {
  count = var.create_nat_gateway ? 1 : 0

  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[0].id
}

resource "aws_route_table_association" "private" {
  count = 3

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_vpc_endpoint" "s3" {
  count = var.create_nat_gateway ? 1 : 0

  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.eu-west-2.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id, aws_route_table.public[0].id]

  tags = merge(local.tags, { Name = "${var.project}-${var.environment}-s3-endpoint" })
}
