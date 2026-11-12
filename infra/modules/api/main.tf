locals {
  # Lambda-t e APP backend (app/backend/*.py):
  # - consumption lexon gold CSV nga S3
  # - forecast dhe anomalies lexojnë rezultatet ML nga DynamoDB (fallback te fixtures)
  # /chat shkon direkt te Lambda e assistant-it (GenAI), shih më poshtë.
  functions = {
    consumption = { handler = "app.backend.consumption.handler", method = "GET", path = "/consumption" }
    anomalies   = { handler = "app.backend.anomalies.handler", method = "GET", path = "/anomalies" }
    forecast    = { handler = "app.backend.forecast.handler", method = "GET", path = "/forecast" }
  }

  # Extract table names from ARNs
  table_names = {
    for key, arn in var.dynamodb_table_arns :
    key => split("/", arn)[1]
  }
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.name_prefix}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access policy
data "aws_iam_policy_document" "dynamodb_access" {
  statement {
    sid    = "DynamoDBAccess"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem"
    ]

    resources = values(var.dynamodb_table_arns)
  }
}

resource "aws_iam_policy" "dynamodb_access" {
  name        = "${var.name_prefix}-lambda-dynamodb"
  description = "Allow Lambda functions to access DynamoDB tables"
  policy      = data.aws_iam_policy_document.dynamodb_access.json
}

resource "aws_iam_role_policy_attachment" "dynamodb" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.dynamodb_access.arn
}

# S3 access policy për gold data (Developer A)
data "aws_iam_policy_document" "s3_gold_access" {
  statement {
    sid    = "S3GoldDataRead"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]

    # Allow reading gold CSV exports (Developer A)
    resources = [
      "arn:aws:s3:::g2-greentrack-gold-886565871385",
      "arn:aws:s3:::g2-greentrack-gold-886565871385/exports/*"
    ]
  }
}

resource "aws_iam_policy" "s3_gold_access" {
  name        = "${var.name_prefix}-lambda-s3-gold"
  description = "Allow Lambda functions to read gold data from S3"
  policy      = data.aws_iam_policy_document.s3_gold_access.json
}

resource "aws_iam_role_policy_attachment" "s3_gold" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.s3_gold_access.arn
}

# Lambda package is pre-built using scripts/build-lambda.ps1
# This avoids Terraform trying to zip the entire app directory
# which can take a long time and include unnecessary files

resource "aws_lambda_function" "this" {
  for_each         = local.functions
  function_name    = "${var.name_prefix}-${each.key}"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.11"
  handler          = each.value.handler
  filename         = var.package_path
  source_code_hash = filebase64sha256(var.package_path)
  timeout          = 15
  memory_size      = 512 # më shumë CPU për cold start (lexim CSV ~2 MB nga S3)

  # Gold data lexohet si CSV me csv + boto3, prandaj nuk duhet layer pandas/pyarrow.

  environment {
    variables = merge(
      {
        REGION       = "eu-central-1"
        HOUSEHOLD_ID = var.household_id
        GOLD_BUCKET  = "g2-greentrack-gold-886565871385" # Gold CSV exports (Developer A)
        GOLD_PREFIX  = "exports/"
      },
      length(local.table_names) > 0 ? {
        # DynamoDB table names për Lambda environment variables
        DYNAMODB_TABLE_CONSUMPTION = lookup(local.table_names, "consumption", "")
        DYNAMODB_TABLE_ANOMALIES   = lookup(local.table_names, "anomalies", "")
        # Tabela e re forecasts për ML predictions
        DYNAMODB_TABLE_FORECASTS = lookup(local.table_names, "forecasts", "")
      } : {}
    )
  }
}

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
  }
}

resource "aws_apigatewayv2_integration" "this" {
  for_each               = local.functions
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this[each.key].invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "this" {
  for_each  = local.functions
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "${each.value.method} ${each.value.path}"
  target    = "integrations/${aws_apigatewayv2_integration.this[each.key].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api" {
  for_each      = local.functions
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# ---------------------------------------------------------------------------
# /chat -> g2-greentrack-assistant (Lambda e GenAI, menaxhohet jashtë këtij stack-u)
# Handler-i i assistant-it kthen vetë statusCode me payload 2.0.
# ---------------------------------------------------------------------------
data "aws_lambda_function" "assistant" {
  function_name = var.assistant_function_name
}

resource "aws_apigatewayv2_integration" "chat" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = data.aws_lambda_function.assistant.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000 # assistant-i mund të marrë ~10-15 s
}

resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.chat.id}"
}

resource "aws_lambda_permission" "chat" {
  statement_id  = "AllowGreenTrackApiInvokeChat"
  action        = "lambda:InvokeFunction"
  function_name = data.aws_lambda_function.assistant.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/POST/chat"
}

# Route dhe integration ekzistuese ripërdoren (update në vend, pa downtime / konflikt route_key)
moved {
  from = aws_apigatewayv2_route.this["chat"]
  to   = aws_apigatewayv2_route.chat
}

moved {
  from = aws_apigatewayv2_integration.this["chat"]
  to   = aws_apigatewayv2_integration.chat
}