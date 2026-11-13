# Lake Formation permissions per layer (Challenge 2 governance), for our three databases only.
# No account-wide Lake Formation settings are changed here (admins, default permissions).
#
# - Pipeline (Glue) role: full access to bronze, silver and gold (it writes all three).
# - Readers: read-only access to gold (app API, SageMaker, ML inference, Bedrock assistant,
#   CI plan role, and the people who query Athena).
# - enforce_gold = false: grants exist, but IAM still decides access (IAM_ALLOWED_PRINCIPALS kept).
#   enforce_gold = true:  gold's S3 location is registered with Lake Formation and IAM_ALLOWED_PRINCIPALS
#   is revoked on the gold database and its tables, so only the grants below apply.
#   Setting it back to false re-grants IAM_ALLOWED_PRINCIPALS (rollback).
#
# Variables used: var.enforce_gold, var.api_role_name, var.analyst_principal_arns, var.name_prefix.
# Locals:
#   gold_tables   - tables the gold job writes (data/jobs/gold_aggregate.py)
#   gold_readers  - principal ARN per reader (key = short name)
#   layer_tables  - one entry per (layer) for the pipeline's all-tables grants

locals {
  gold_tables = toset([
    "gold_hourly_consumption", "gold_daily_consumption", "gold_peak_hour_stats", "gold_submetering_monthly",
  ])

  role_arn = "arn:aws:iam::${local.account_id}:role"
  gold_readers = merge(
    {
      api       = "${local.role_arn}/${var.api_role_name}"
      sagemaker = "${local.role_arn}/${var.name_prefix}-sagemaker-exec"
      inference = "${local.role_arn}/${var.name_prefix}-ml-inference-lambda"
      assistant = "${local.role_arn}/${var.name_prefix}-assistant-lambda"
      ci_plan   = "${local.role_arn}/${var.name_prefix}-github-plan"
    },
    { for i, arn in var.analyst_principal_arns : "analyst_${i}" => arn },
  )
}

# ---------- Pipeline role: writes all three layers ----------

resource "aws_lakeformation_permissions" "pipeline_database" {
  for_each    = local.layers
  principal   = aws_iam_role.glue.arn
  permissions = ["ALL"]

  database {
    name = aws_glue_catalog_database.this[each.key].name
  }
}

resource "aws_lakeformation_permissions" "pipeline_tables" {
  for_each    = local.layers
  principal   = aws_iam_role.glue.arn
  permissions = ["ALL"]

  table {
    database_name = aws_glue_catalog_database.this[each.key].name
    wildcard      = true
  }
}

# ---------- Readers: gold only, read-only ----------

resource "aws_lakeformation_permissions" "reader_gold_database" {
  for_each    = local.gold_readers
  principal   = each.value
  permissions = ["DESCRIBE"]

  database {
    name = aws_glue_catalog_database.this["gold"].name
  }
}

resource "aws_lakeformation_permissions" "reader_gold_tables" {
  for_each    = local.gold_readers
  principal   = each.value
  permissions = ["SELECT", "DESCRIBE"]

  table {
    database_name = aws_glue_catalog_database.this["gold"].name
    wildcard      = true
  }
}

# ---------- IAM-only access on gold: kept while enforce_gold = false ----------
# These grants already exist (account default); managing them here lets enforce_gold revoke and restore them.

resource "aws_lakeformation_permissions" "gold_iam_allowed_database" {
  count       = var.enforce_gold ? 0 : 1
  principal   = "IAM_ALLOWED_PRINCIPALS"
  permissions = ["ALL"]

  database {
    name = aws_glue_catalog_database.this["gold"].name
  }
}

resource "aws_lakeformation_permissions" "gold_iam_allowed_tables" {
  for_each    = var.enforce_gold ? toset([]) : local.gold_tables
  principal   = "IAM_ALLOWED_PRINCIPALS"
  permissions = ["ALL"]

  table {
    database_name = aws_glue_catalog_database.this["gold"].name
    name          = each.key
  }
}

# ---------- Enforcement on gold: register the bucket with Lake Formation ----------

data "aws_iam_policy_document" "lf_gold_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lakeformation.amazonaws.com"]
    }
  }
}

# Role Lake Formation uses to read and write the gold bucket for granted principals.
resource "aws_iam_role" "lf_gold" {
  count              = var.enforce_gold ? 1 : 0
  name               = "${var.name_prefix}-lf-gold-access"
  assume_role_policy = data.aws_iam_policy_document.lf_gold_assume.json
}

data "aws_iam_policy_document" "lf_gold_s3" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.this["gold"].arn]
  }

  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.this["gold"].arn}/*"]
  }
}

resource "aws_iam_role_policy" "lf_gold" {
  count  = var.enforce_gold ? 1 : 0
  name   = "${var.name_prefix}-lf-gold-s3"
  role   = aws_iam_role.lf_gold[0].id
  policy = data.aws_iam_policy_document.lf_gold_s3.json
}

resource "aws_lakeformation_resource" "gold" {
  count    = var.enforce_gold ? 1 : 0
  arn      = aws_s3_bucket.this["gold"].arn
  role_arn = aws_iam_role.lf_gold[0].arn

  depends_on = [aws_iam_role_policy.lf_gold]
}

# The pipeline writes gold files, so it needs data location access once gold is registered.
resource "aws_lakeformation_permissions" "pipeline_gold_location" {
  count       = var.enforce_gold ? 1 : 0
  principal   = aws_iam_role.glue.arn
  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    arn = aws_lakeformation_resource.gold[0].arn
  }
}
