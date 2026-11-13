# Inference: serverless SageMaker endpoints for XGBoost and RCF, and the Lambda that calls them
# (Challenge 3: a Lambda call returns a forecast and anomaly scores for a time window).
# Variables used: var.name_prefix, var.enable_endpoints, var.xgboost_image, var.xgboost_model_data,
# var.rcf_image, var.rcf_model_data, var.serverless_memory_mb, var.serverless_max_concurrency.
# Locals: names of the data stack (modules/data naming: <prefix>-<name>-<account>), endpoint names,
# a short hash of each model artifact so a new artifact gets a new model/config name.

data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region

  gold_bucket      = "${var.name_prefix}-gold-${local.account_id}"
  artifacts_bucket = "${var.name_prefix}-artifacts-${local.account_id}"
  gold_database    = "${replace(var.name_prefix, "-", "_")}_gold"
  athena_workgroup = "${var.name_prefix}-analytics"

  models = {
    xgboost = { image = var.xgboost_image, data = var.xgboost_model_data }
    rcf     = { image = var.rcf_image, data = var.rcf_model_data }
  }
  endpoint_names = { for key, _ in local.models : key => "${var.name_prefix}-${key}-serverless" }
  params_key     = "inference/params.json"
  lambda_name    = "${var.name_prefix}-ml-inference"
}

# Fail at plan time if the data stack is not deployed (read-only lookups).
data "aws_s3_bucket" "gold" {
  bucket = local.gold_bucket
}

data "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket
}

# ---------- SageMaker models and serverless endpoints ----------

resource "aws_sagemaker_model" "this" {
  for_each           = local.models
  name               = "${var.name_prefix}-${each.key}-${substr(md5(each.value.data), 0, 8)}"
  execution_role_arn = aws_iam_role.sagemaker.arn

  primary_container {
    image          = each.value.image
    model_data_url = each.value.data
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint_configuration" "this" {
  for_each = local.models
  name     = "${var.name_prefix}-${each.key}-${substr(md5(each.value.data), 0, 8)}"

  production_variants {
    variant_name = "AllTraffic"
    model_name   = aws_sagemaker_model.this[each.key].name

    # Scales to zero when idle: no endpoint compute is billed at rest.
    serverless_config {
      memory_size_in_mb = var.serverless_memory_mb
      max_concurrency   = var.serverless_max_concurrency
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "this" {
  for_each             = var.enable_endpoints ? local.models : {}
  name                 = local.endpoint_names[each.key]
  endpoint_config_name = aws_sagemaker_endpoint_configuration.this[each.key].name
}

# ---------- Lambda ----------

# Only the inference package goes into the zip (standard library + boto3, which the runtime provides).
data "archive_file" "inference" {
  type        = "zip"
  output_path = "${path.module}/.build/ml-inference.zip"

  source {
    content  = file("${path.module}/../../../ml/__init__.py")
    filename = "ml/__init__.py"
  }

  dynamic "source" {
    for_each = toset(["__init__.py", "aws.py", "core.py", "handler.py"])
    content {
      content  = file("${path.module}/../../../ml/inference/${source.value}")
      filename = "ml/inference/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "inference" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "inference" {
  function_name    = local.lambda_name
  role             = aws_iam_role.inference.arn
  runtime          = "python3.12"
  handler          = "ml.inference.handler.lambda_handler"
  filename         = data.archive_file.inference.output_path
  source_code_hash = data.archive_file.inference.output_base64sha256
  timeout          = 120
  memory_size      = 256

  environment {
    variables = {
      XGBOOST_ENDPOINT = local.endpoint_names["xgboost"]
      RCF_ENDPOINT     = local.endpoint_names["rcf"]
      ATHENA_DATABASE  = local.gold_database
      ATHENA_WORKGROUP = local.athena_workgroup
      PARAMS_BUCKET    = aws_s3_bucket.ml.bucket
      PARAMS_KEY       = local.params_key
    }
  }

  depends_on = [aws_cloudwatch_log_group.inference, aws_iam_role_policy.inference]
}

# ---------- Lambda role (least privilege) ----------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "inference" {
  name               = "${local.lambda_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "inference" {
  # Needed only when the gold location is registered with Lake Formation (enforce_gold in infra/data).
  statement {
    sid       = "LakeFormationDataAccess"
    actions   = ["lakeformation:GetDataAccess"]
    resources = ["*"]
  }

  statement {
    sid       = "InvokeEndpoints"
    actions   = ["sagemaker:InvokeEndpoint"]
    resources = [for name in values(local.endpoint_names) : "arn:aws:sagemaker:${local.region}:${local.account_id}:endpoint/${name}"]
  }

  statement {
    sid       = "AthenaQueries"
    actions   = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution"]
    resources = ["arn:aws:athena:${local.region}:${local.account_id}:workgroup/${local.athena_workgroup}"]
  }

  statement {
    sid     = "GoldCatalog"
    actions = ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"]
    resources = [
      "arn:aws:glue:${local.region}:${local.account_id}:catalog",
      "arn:aws:glue:${local.region}:${local.account_id}:database/${local.gold_database}",
      "arn:aws:glue:${local.region}:${local.account_id}:table/${local.gold_database}/*",
    ]
  }

  # Athena reads the Gold table files with the caller's permissions.
  statement {
    sid       = "GoldRead"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:GetObject"]
    resources = [data.aws_s3_bucket.gold.arn, "${data.aws_s3_bucket.gold.arn}/*"]
  }

  # Query results go to the location enforced by the workgroup (modules/data).
  statement {
    sid       = "AthenaResultsBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [data.aws_s3_bucket.artifacts.arn]
  }

  statement {
    sid       = "AthenaResultsObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${data.aws_s3_bucket.artifacts.arn}/athena-results/*"]
  }

  statement {
    sid       = "Params"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.ml.arn}/${local.params_key}"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.inference.arn}:*"]
  }
}

resource "aws_iam_role_policy" "inference" {
  name   = "${local.lambda_name}-lambda"
  role   = aws_iam_role.inference.id
  policy = data.aws_iam_policy_document.inference.json
}

# Training can read Gold exports directly from S3 (promised in the DATA-06 review).
data "aws_iam_policy_document" "sagemaker_gold" {
  # Needed only when the gold location is registered with Lake Formation (enforce_gold in infra/data).
  statement {
    sid       = "LakeFormationDataAccess"
    actions   = ["lakeformation:GetDataAccess"]
    resources = ["*"]
  }

  statement {
    sid       = "GoldExportsList"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [data.aws_s3_bucket.gold.arn]
  }

  statement {
    sid       = "GoldExportsRead"
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.gold.arn}/exports/*"]
  }
}

resource "aws_iam_role_policy" "sagemaker_gold" {
  name   = "${var.name_prefix}-sagemaker-gold-read"
  role   = aws_iam_role.sagemaker.id
  policy = data.aws_iam_policy_document.sagemaker_gold.json
}
