# Module: vpc

Creates the core network foundation - a VPC across three AZs with public and private subnets, an Internet Gateway, a NAT Gateway, and an S3 Gateway Endpoint.

## Resources

| Resource | Name pattern | Notes |
|---|---|---|
| `aws_vpc` | `{project}-{env}-vpc` | DNS hostnames and support enabled |
| `aws_subnet` (×3 public) | `{project}-{env}-public-{1,2,3}` | One per AZ, auto-assigns public IP |
| `aws_subnet` (×3 private) | `{project}-{env}-private-{1,2,3}` | One per AZ, no public IP |
| `aws_internet_gateway` | `{project}-{env}-igw` | Attached to VPC |
| `aws_eip` | `{project}-{env}-nat-eip` | Elastic IP for NAT Gateway |
| `aws_nat_gateway` | `{project}-{env}-nat` | Single NAT in first public subnet - see note below |
| `aws_route_table` (public) | `{project}-{env}-public-rt` | Routes `0.0.0.0/0` → IGW |
| `aws_route_table` (private) | `{project}-{env}-private-rt` | Routes `0.0.0.0/0` → NAT |
| `aws_vpc_endpoint` (S3) | `{project}-{env}-s3-endpoint` | Gateway endpoint - avoids NAT charges for S3 traffic |

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `project` | `string` | - | Project name used in resource names and tags |
| `environment` | `string` | - | Environment name (`dev`, `preprod`, `prod`) |
| `vpc_cidr` | `string` | `"10.0.0.0/16"` | VPC CIDR block |
| `public_subnet_cidrs` | `list(string)` | `["10.0.1.0/24","10.0.2.0/24","10.0.3.0/24"]` | One CIDR per AZ |
| `private_subnet_cidrs` | `list(string)` | `["10.0.11.0/24","10.0.12.0/24","10.0.13.0/24"]` | One CIDR per AZ |
| `availability_zones` | `list(string)` | `["eu-west-2a","eu-west-2b","eu-west-2c"]` | AZs to deploy into |

## Outputs

| Name | Description |
|---|---|
| `vpc_id` | ID of the VPC |
| `public_subnet_ids` | List of public subnet IDs |
| `private_subnet_ids` | List of private subnet IDs |
| `nat_gateway_id` | ID of the NAT Gateway |
| `s3_endpoint_id` | ID of the S3 Gateway VPC endpoint |

## Design notes

**Single NAT Gateway** - all three private subnets share one NAT Gateway in the first public subnet. This is a deliberate cost-saving choice. For production with strict availability requirements, consider one NAT Gateway per AZ (add `count = 3` to `aws_eip` and `aws_nat_gateway`, and a route table per private subnet).

**S3 Gateway Endpoint** - routes S3 API calls through the AWS private backbone rather than through the NAT Gateway, eliminating NAT data-transfer charges for S3.

## Used by

- [security](../security/) - passes `vpc_id` for security group creation
- [compute](../compute/) - passes `vpc_id` and `private_subnet_ids` for Lambda and EC2 runner placement
