# Module: compute

Deploys the serverless backend and CI/CD runner:

- **Lambda** - Python 3.12 spatial index calculation function in private subnets, behind API Gateway with WAF
- **API Gateway** - REST API (proxy integration) with regional WAF attached
- **EC2 GitHub Actions Runner** - Amazon Linux 2023 instance in a private subnet, registered to the repository via a PAT stored in SSM

## Resources

### Lambda

| Resource | Notes |
|---|---|
| `aws_lambda_function` (`{project}-{env}-spatial-index`) | Python 3.12, 30s timeout, 256 MB, VPC-attached |
| `aws_iam_role` (lambda-exec) | Assumes `lambda.amazonaws.com`; VPC + basic execution policies attached |
| `data.archive_file` (placeholder) | Minimal `handler.py` zip - replace via CI on first real deploy |

### API Gateway

| Resource | Notes |
|---|---|
| `aws_api_gateway_rest_api` | `{project}-{env}-api` |
| `aws_api_gateway_resource` | `{proxy+}` - catches all paths |
| `aws_api_gateway_method` | `ANY`, API key required |
| `aws_api_gateway_integration` | Lambda proxy (`AWS_PROXY`) |
| `aws_api_gateway_stage` | Stage name = environment (`dev` / `preprod` / `prod`) |
| `aws_wafv2_web_acl_association` | Attaches regional WAF to the stage |
| `aws_api_gateway_api_key` | `{project}-{env}-api-key` - callers must supply `x-api-key` header |
| `aws_api_gateway_usage_plan` | Binds the API key to the stage |

### EC2 GitHub Actions Runner

| Resource | Notes |
|---|---|
| `aws_instance` | Amazon Linux 2023, `t3.small`, first private subnet, IMDSv2 required, hop limit = 1 |
| `aws_iam_role` (runner) | `AmazonSSMManagedInstanceCore` + scoped SSM read policy |
| `aws_iam_instance_profile` | Wraps the runner role |
| `aws_ssm_parameter` (`/{project}/{env}/github-runner-pat`) | `SecureString` - PAT never written to user_data |

The runner user_data is templated from [templates/runner_userdata.sh.tpl](templates/runner_userdata.sh.tpl). At boot it:
1. Installs Docker and Git via `dnf`
2. Fetches the PAT from SSM at runtime (`aws ssm get-parameter --with-decryption`)
3. Downloads the latest GitHub Actions runner binary
4. Registers with `config.sh --unattended` and installs as a systemd service

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `project` | `string` | - | Project name |
| `environment` | `string` | - | Environment (`dev`, `preprod`, `prod`) |
| `vpc_id` | `string` | - | VPC ID from [vpc](../vpc/) |
| `private_subnet_ids` | `list(string)` | - | Private subnet IDs from [vpc](../vpc/) |
| `lambda_sg_id` | `string` | - | Lambda security group ID from [security](../security/) |
| `runner_sg_id` | `string` | - | Runner security group ID from [security](../security/) |
| `waf_regional_arn` | `string` | - | Regional WAF ARN from [security](../security/) |
| `lambda_timeout` | `number` | `30` | Lambda timeout in seconds |
| `lambda_memory_size` | `number` | `256` | Lambda memory in MB |
| `lambda_runtime` | `string` | `"python3.12"` | Lambda runtime |
| `runner_instance_type` | `string` | `"t3.small"` | EC2 instance type for the runner |
| `runner_pat_token` | `string` (sensitive) | `""` | GitHub PAT for runner registration. Leave empty to skip runner deployment. **Supply via `TF_VAR_runner_pat_token` only - never hardcode.** |
| `github_org` | `string` | `"PMO-Data-Science"` | GitHub organisation |
| `github_repo` | `string` | - | Repository name (without org prefix) |

## Outputs

| Name | Description |
|---|---|
| `lambda_function_arn` | ARN of the spatial index Lambda |
| `lambda_function_name` | Name of the spatial index Lambda |
| `api_gateway_url` | Invoke URL - `https://{id}.execute-api.eu-west-2.amazonaws.com/{env}` |
| `api_gateway_id` | REST API ID |
| `api_key_id` | API Gateway key ID - retrieve the value with `aws apigateway get-api-key --api-key <id> --include-value` |
| `runner_instance_id` | EC2 instance ID of the runner (sensitive, null if runner not deployed) |

## Dependencies

| Input | Source module | Output |
|---|---|---|
| `vpc_id`, `private_subnet_ids` | [vpc](../vpc/) | `vpc_id`, `private_subnet_ids` |
| `lambda_sg_id`, `runner_sg_id`, `waf_regional_arn` | [security](../security/) | same |

## PAT token handling

The GitHub PAT is **never** stored in Terraform state as plaintext. Flow:

```
CI sets TF_VAR_runner_pat_token=${{ secrets.RUNNER_PAT }}
  → Terraform writes it to SSM SecureString (KMS-encrypted at rest)
  → EC2 user_data calls: aws ssm get-parameter --with-decryption
  → PAT is used in memory to register the runner, never written to disk
```

To rotate the PAT: update the SSM parameter value and re-run the runner registration (either re-apply or re-run the user_data script manually via SSM Session Manager).

## Accessing the runner

The runner has no SSH ingress rule. Use **SSM Session Manager** instead:

```bash
aws ssm start-session --target <runner_instance_id> --region eu-west-2
```
