data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # One bucket per layer, plus one for Glue scripts and Athena results.
  # The account id makes the names unique worldwide.
  buckets = toset(["bronze", "silver", "gold", "artifacts"])
  bucket  = { for name in local.buckets : name => "${var.name_prefix}-${name}-${local.account_id}" }

  # Glue/Athena database names may not contain "-", so the prefix uses "_".
  db_prefix = replace(var.name_prefix, "-", "_")
  layers    = toset(["bronze", "silver", "gold"])
  database  = { for layer in local.layers : layer => "${local.db_prefix}_${layer}" }

  bronze_columns = [
    "Date", "Time", "Global_active_power", "Global_reactive_power", "Voltage",
    "Global_intensity", "Sub_metering_1", "Sub_metering_2", "Sub_metering_3",
    "source_file", "load_timestamp",
  ]

  scripts = {
    bronze = "glue_bronze.py"
    silver = "silver_clean.py"
    gold   = "gold_aggregate.py"
  }

  # Arguments each Glue job receives (the scripts read them with argparse).
  job_arguments = {
    bronze = {
      "--raw_path"    = "s3://${local.bucket["bronze"]}/incoming/${var.raw_file_name}"
      "--bronze_path" = "s3://${local.bucket["bronze"]}/household_power/"
    }
    silver = {
      "--catalog"     = "glue"
      "--bronze_path" = "s3://${local.bucket["bronze"]}/household_power/"
      "--warehouse"   = "s3://${local.bucket["silver"]}/warehouse/"
      "--silver_db"   = local.database["silver"]
    }
    gold = {
      "--catalog"    = "glue"
      "--warehouse"  = "s3://${local.bucket["gold"]}/warehouse/"
      "--silver_db"  = local.database["silver"]
      "--gold_db"    = local.database["gold"]
      "--export_dir" = "s3://${local.bucket["gold"]}/exports"
    }
  }
}

# ---------- S3: where the data lives ----------

resource "aws_s3_bucket" "this" {
  for_each      = local.buckets
  bucket        = local.bucket[each.key]
  force_destroy = true # lets `terraform destroy` remove buckets that still contain files
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each                = local.buckets
  bucket                  = aws_s3_bucket.this[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.this[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# The pipeline scripts, uploaded so Glue can run them.
resource "aws_s3_object" "script" {
  for_each = local.scripts
  bucket   = aws_s3_bucket.this["artifacts"].id
  key      = "glue-scripts/${each.value}"
  source   = "${var.jobs_dir}/${each.value}"
  etag     = filemd5("${var.jobs_dir}/${each.value}") # re-upload when the file changes
}

# ---------- Glue Data Catalog: the list of tables ----------

resource "aws_glue_catalog_database" "this" {
  for_each = local.layers
  name     = local.database[each.key]
}

# Bronze is plain Parquet (not Iceberg), so its table is described here.
# Silver and gold are Iceberg tables: the Glue jobs register them themselves.
resource "aws_glue_catalog_table" "bronze" {
  name          = "household_power"
  database_name = aws_glue_catalog_database.this["bronze"].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL       = "TRUE"
    classification = "parquet"
  }

  storage_descriptor {
    location      = "s3://${local.bucket["bronze"]}/household_power/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    dynamic "columns" {
      for_each = local.bronze_columns
      content {
        name = lower(columns.value)
        type = "string"
      }
    }
  }
}

# ---------- IAM permissions----------

data "aws_iam_policy_document" "glue_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${var.name_prefix}-glue-pipeline"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

# Logs, metrics and Glue Data Catalog access.
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Read/write only our own buckets.
data "aws_iam_policy_document" "glue_s3" {
  statement {
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [for b in aws_s3_bucket.this : b.arn]
  }

  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [for b in aws_s3_bucket.this : "${b.arn}/*"]
  }
}

resource "aws_iam_role_policy" "glue_s3" {
  name   = "${var.name_prefix}-glue-s3"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_s3.json
}

# ---------- Glue jobs: the pipeline steps ----------

resource "aws_glue_job" "this" {
  for_each          = local.scripts
  name              = "${var.name_prefix}-${each.key}"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "5.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  timeout           = 30 # minutes

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.this["artifacts"].id}/${aws_s3_object.script[each.key].key}"
    python_version  = "3"
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--datalake-formats"                 = "iceberg"
      "--enable-continuous-cloudwatch-log" = "true"
      "--TempDir"                          = "s3://${aws_s3_bucket.this["artifacts"].id}/glue-temp/"
    },
    local.job_arguments[each.key]
  )
}

# ---------- Athena: SQL on the tables ----------

resource "aws_athena_workgroup" "this" {
  name          = "${var.name_prefix}-analytics"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.this["artifacts"].id}/athena-results/"
    }
  }
}