# Module: security

Creates WAFv2 WebACLs and egress-only security groups. No public ingress is permitted on any security group.

> **Provider alias required.** CloudFront WAF must reside in `us-east-1` (hard AWS requirement). The caller must supply an aliased `aws.us_east_1` provider - see [Caller setup](#caller-setup) below.

## Resources

| Resource | Name pattern | Notes |
|---|---|---|
| `aws_wafv2_web_acl` (CloudFront) | `{project}-{env}-cloudfront-waf` | `scope = CLOUDFRONT`, deployed via `aws.us_east_1` provider |
| `aws_wafv2_web_acl` (Regional) | `{project}-{env}-regional-waf` | `scope = REGIONAL`, eu-west-2, attached to API Gateway |
| `aws_security_group` (Lambda) | `{project}-{env}-lambda-sg` | Egress 443 only, no ingress |
| `aws_security_group` (Runner) | `{project}-{env}-runner-sg` | Egress 443 only, no ingress |

Both WAFs use the `AWSManagedRulesCommonRuleSet` with CloudWatch metrics enabled.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `project` | `string` | - | Project name used in resource names and tags |
| `environment` | `string` | - | Environment name (`dev`, `preprod`, `prod`) |
| `vpc_id` | `string` | - | VPC ID for security group scope |

## Outputs

| Name | Description |
|---|---|
| `waf_cloudfront_arn` | ARN of the us-east-1 WAFv2 WebACL (pass to [cdn](../cdn/)) |
| `waf_regional_arn` | ARN of the regional WAFv2 WebACL (pass to [compute](../compute/)) |
| `lambda_sg_id` | Security group ID for Lambda functions (pass to [compute](../compute/)) |
| `runner_sg_id` | Security group ID for the GitHub Actions runner (pass to [compute](../compute/)) |

## Caller setup

This module declares `aws.us_east_1` as a `configuration_alias`. The Terragrunt caller must generate a second provider block and pass both providers to the module. In [live/{env}/security/terragrunt.hcl](../../live/dev/security/terragrunt.hcl) this is handled via a `generate` block:

```hcl
generate "provider_us_east_1" {
  path      = "provider_us_east_1.tf"
  if_exists = "overwrite"
  contents  = <<-EOF
    provider "aws" {
      alias  = "us_east_1"
      region = "us-east-1"
    }
  EOF
}
```

## Dependencies

| Input | Source module | Output |
|---|---|---|
| `vpc_id` | [vpc](../vpc/) | `vpc_id` |

## Used by

- [compute](../compute/) - `lambda_sg_id`, `runner_sg_id`, `waf_regional_arn`
- [cdn](../cdn/) - `waf_cloudfront_arn`
