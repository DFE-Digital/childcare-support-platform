locals {
  tags = {
    Project     = var.project
    Environment = var.environment
  }

  name_prefix   = "${var.project}-${var.environment}"
  deploy_runner = var.runner_pat_token != "" ? 1 : 0
}

# -----------------------------------------------------------------------------
# Lambda - Spatial Index Calculation
# -----------------------------------------------------------------------------

data "archive_file" "lambda_placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  # provided.al2023 custom runtime requires a file named "bootstrap".
  # This placeholder is only used during initial terraform apply — the real
  # Rust binary is deployed immediately after via `make sis/deploy`.
  source {
    content  = "#!/bin/sh\nexit 1\n"
    filename = "bootstrap"
  }
}

resource "aws_iam_role" "lambda_exec" {
  name = "${local.name_prefix}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "main" {
  function_name    = "${local.name_prefix}-spatial-index"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = var.lambda_runtime
  handler          = "bootstrap"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = {
      SIS_API_TYPE = "lambda"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_sg_id]
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# API Gateway REST API with Lambda proxy integration
# -----------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "main" {
  name = "${local.name_prefix}-api"

  binary_media_types = ["*/*"]

  tags = local.tags
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.proxy.id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.main.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [aws_api_gateway_integration.lambda]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_rest_api.main.binary_media_types,
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  deployment_id = aws_api_gateway_deployment.main.id
  stage_name    = var.environment

  tags = local.tags
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.main.arn
  web_acl_arn  = var.waf_regional_arn
}

# -----------------------------------------------------------------------------
# API Gateway - API Key + Usage Plan
# Callers must supply x-api-key header. The key value is stored in SSM after
# creation and can be retrieved via: aws apigateway get-api-key --api-key <id> --include-value
# -----------------------------------------------------------------------------

resource "aws_api_gateway_api_key" "main" {
  name = "${local.name_prefix}-api-key"
  tags = local.tags
}

resource "aws_api_gateway_usage_plan" "main" {
  name = "${local.name_prefix}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.main.stage_name
  }

  tags = local.tags
}

resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.main.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main.id
}

# Store the API key value in SSM so the CDN module can read it at plan time
# and bake it into a CloudFront Function (never exposed client-side).
resource "aws_ssm_parameter" "api_key" {
  name  = "/${var.project}/${var.environment}/api-key"
  type  = "SecureString"
  value = aws_api_gateway_api_key.main.value

  tags = local.tags
}

# -----------------------------------------------------------------------------
# EC2 GitHub Actions Runner
# -----------------------------------------------------------------------------

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# PAT stored in SSM SecureString - never injected into user_data as plaintext
resource "aws_ssm_parameter" "runner_pat" {
  count = local.deploy_runner

  name  = "/${var.project}/${var.environment}/github-runner-pat"
  type  = "SecureString"
  value = var.runner_pat_token

  tags = local.tags
}

resource "aws_iam_role" "runner" {
  count = local.deploy_runner

  name = "${local.name_prefix}-runner"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

# SSM Session Manager - SSH-free access to the runner from the console
resource "aws_iam_role_policy_attachment" "runner_ssm_core" {
  count = local.deploy_runner

  role       = aws_iam_role.runner[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Scoped policy: only allow reading the runner PAT parameter
resource "aws_iam_policy" "runner_ssm_read" {
  count = local.deploy_runner

  name = "${local.name_prefix}-runner-ssm-read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "ssm:GetParameter"
      Resource = aws_ssm_parameter.runner_pat[0].arn
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "runner_ssm_read" {
  count = local.deploy_runner

  role       = aws_iam_role.runner[0].name
  policy_arn = aws_iam_policy.runner_ssm_read[0].arn
}

resource "aws_iam_instance_profile" "runner" {
  count = local.deploy_runner

  name = "${local.name_prefix}-runner"
  role = aws_iam_role.runner[0].name
}

resource "aws_instance" "runner" {
  count = local.deploy_runner

  ami                    = data.aws_ami.al2023.id
  instance_type          = var.runner_instance_type
  subnet_id              = var.private_subnet_ids[0]
  vpc_security_group_ids = [var.runner_sg_id]
  iam_instance_profile   = aws_iam_instance_profile.runner[0].name

  user_data = base64encode(templatefile("${path.module}/templates/runner_userdata.sh.tpl", {
    project      = var.project
    environment  = var.environment
    github_org   = var.github_org
    github_repo  = var.github_repo
    aws_region   = "eu-west-2"
    ssm_pat_name = aws_ssm_parameter.runner_pat[0].name
  }))

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # prevents SSRF token relay
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-github-runner" })
}
