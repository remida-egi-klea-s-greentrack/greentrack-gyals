# GenAI module (Developer B): Bedrock guardrail and the assistant Lambda (Challenge 4).
# Variables used: var.name_prefix, var.model_id, var.gold_database, var.athena_workgroup,
# var.gold_bucket_arn, var.artifacts_bucket_arn, var.inference_lambda_arn, var.inference_lambda_name
# (Knowledge Base for energy-saving advice: knowledge_base.tf).
# Locals: refusal text shown when the guardrail blocks a request, Lambda name, model id without the
# cross-region prefix (the eu. inference profile routes to the same model in several EU regions),
# denied guardrail topics.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  region        = data.aws_region.current.region
  lambda_name   = "${var.name_prefix}-assistant"
  refusal       = "I can only answer questions about this household's electricity consumption data."
  base_model_id = trimprefix(var.model_id, "eu.")

  denied_topics = {
    "programming-help" = {
      definition = "Requests to write, explain or debug software code or scripts."
      examples   = ["Write me a Python script to sort a list", "Fix this JavaScript error"]
    }
    "politics" = {
      definition = "Questions about elections, political parties, politicians or political opinions."
      examples   = ["Which political party should I vote for?", "What do you think of the president?"]
    }
    "investment-advice" = {
      definition = "Advice on buying or selling stocks, cryptocurrencies or other investments."
      examples   = ["Which stocks should I buy this year?", "Should I invest in bitcoin?"]
    }
    "medical-legal-advice" = {
      definition = "Requests for medical diagnoses or treatment, or for legal advice."
      examples   = ["What medicine should I take for a headache?", "Can I sue my landlord?"]
    }
  }
}

# ---------- Guardrail ----------

resource "aws_bedrock_guardrail" "assistant" {
  name                      = "${var.name_prefix}-assistant"
  description               = "Keeps the GreenTrack assistant on topic and blocks prompt attacks and harmful content."
  blocked_input_messaging   = local.refusal
  blocked_outputs_messaging = local.refusal

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    dynamic "filters_config" {
      for_each = toset(["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"])
      content {
        type            = filters_config.value
        input_strength  = "MEDIUM"
        output_strength = "MEDIUM"
      }
    }
  }

  # Topics are described by what they are (classifiers handle "anything except X" badly).
  # Other off-topic questions are refused by the system prompt.
  topic_policy_config {
    dynamic "topics_config" {
      for_each = local.denied_topics
      content {
        name       = topics_config.key
        type       = "DENY"
        definition = topics_config.value.definition
        examples   = topics_config.value.examples
      }
    }
  }
}

# A fixed version, so a later edit of the draft guardrail does not change the running assistant.
# Any guardrail change publishes a new version, which the Lambda then uses.
resource "aws_bedrock_guardrail_version" "assistant" {
  guardrail_arn = aws_bedrock_guardrail.assistant.guardrail_arn
  description   = "Version used by the assistant Lambda"

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.assistant]
  }
}

# ---------- Lambda ----------

data "archive_file" "assistant" {
  type        = "zip"
  output_path = "${path.module}/.build/assistant.zip"

  dynamic "source" {
    for_each = toset([
      "ml/__init__.py",
      "ml/inference/__init__.py",
      "ml/inference/aws.py",
      "genai/assistant/__init__.py",
      "genai/assistant/agent.py",
      "genai/assistant/handler.py",
      "genai/assistant/tools.py",
    ])
    content {
      content  = file("${path.module}/../../../${source.value}")
      filename = source.value
    }
  }
}

resource "aws_cloudwatch_log_group" "assistant" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "assistant" {
  function_name    = local.lambda_name
  role             = aws_iam_role.assistant.arn
  runtime          = "python3.12"
  handler          = "genai.assistant.handler.lambda_handler"
  filename         = data.archive_file.assistant.output_path
  source_code_hash = data.archive_file.assistant.output_base64sha256
  timeout          = 120
  memory_size      = 256

  environment {
    variables = {
      MODEL_ID           = var.model_id
      GUARDRAIL_ID       = aws_bedrock_guardrail.assistant.guardrail_id
      GUARDRAIL_VERSION  = aws_bedrock_guardrail_version.assistant.version
      ATHENA_DATABASE    = var.gold_database
      ATHENA_WORKGROUP   = var.athena_workgroup
      INFERENCE_FUNCTION = var.inference_lambda_name
      KNOWLEDGE_BASE_ID  = aws_bedrockagent_knowledge_base.energy.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.assistant, aws_iam_role_policy.assistant]
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

resource "aws_iam_role" "assistant" {
  name               = "${local.lambda_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "assistant" {
  # Needed only when the gold location is registered with Lake Formation (enforce_gold in infra/data).
  statement {
    sid       = "LakeFormationDataAccess"
    actions   = ["lakeformation:GetDataAccess"]
    resources = ["*"]
  }

  # Converse needs InvokeModel on the inference profile and on the model in each EU region it routes to.
  statement {
    sid     = "InvokeClaude"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/${var.model_id}",
      "arn:aws:bedrock:*::foundation-model/${local.base_model_id}",
    ]
  }

  statement {
    sid       = "ApplyGuardrail"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [aws_bedrock_guardrail.assistant.guardrail_arn]
  }

  statement {
    sid       = "AthenaQueries"
    actions   = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution"]
    resources = ["arn:aws:athena:${local.region}:${local.account_id}:workgroup/${var.athena_workgroup}"]
  }

  statement {
    sid     = "GoldCatalog"
    actions = ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"]
    resources = [
      "arn:aws:glue:${local.region}:${local.account_id}:catalog",
      "arn:aws:glue:${local.region}:${local.account_id}:database/${var.gold_database}",
      "arn:aws:glue:${local.region}:${local.account_id}:table/${var.gold_database}/*",
    ]
  }

  statement {
    sid       = "GoldRead"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:GetObject"]
    resources = [var.gold_bucket_arn, "${var.gold_bucket_arn}/*"]
  }

  statement {
    sid       = "AthenaResultsBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.artifacts_bucket_arn]
  }

  statement {
    sid       = "AthenaResultsObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.artifacts_bucket_arn}/athena-results/*"]
  }

  statement {
    sid       = "EnergyAdvice"
    actions   = ["bedrock:Retrieve"]
    resources = [aws_bedrockagent_knowledge_base.energy.arn]
  }

  statement {
    sid       = "ForecastAndAnomalies"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.inference_lambda_arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.assistant.arn}:*"]
  }
}

resource "aws_iam_role_policy" "assistant" {
  name   = "${local.lambda_name}-lambda"
  role   = aws_iam_role.assistant.id
  policy = data.aws_iam_policy_document.assistant.json
}
