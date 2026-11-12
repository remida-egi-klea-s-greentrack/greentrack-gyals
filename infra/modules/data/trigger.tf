# Automatic pipeline: a new file in s3://<bronze>/incoming/ starts bronze -> silver -> gold.

# S3 -> EventBridge: the bronze bucket sends its events to EventBridge.
resource "aws_s3_bucket_notification" "bronze" {
  bucket      = aws_s3_bucket.this["bronze"].id
  eventbridge = true
}

# ---------- Step Functions: the pipeline order ----------

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = aws_iam_role.sfn.arn

  definition = jsonencode({
    Comment = "Bronze -> silver -> gold for a new file in incoming/"
    StartAt = "Bronze"
    States = {
      Bronze = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.this["bronze"].name
          Arguments = {
            "--raw_path.$" = "States.Format('s3://{}/{}', $.detail.bucket.name, $.detail.object.key)"
          }
        }
        Next = "Silver"
      }
      Silver = {
        Type       = "Task"
        Resource   = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = { JobName = aws_glue_job.this["silver"].name }
        Next       = "Gold"
      }
      Gold = {
        Type       = "Task"
        Resource   = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = { JobName = aws_glue_job.this["gold"].name }
        End        = true
      }
    }
  })
}

# Step Functions may only start and watch our three Glue jobs.
data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${var.name_prefix}-pipeline-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn_glue" {
  statement {
    actions   = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
    resources = [for job in aws_glue_job.this : job.arn]
  }
}

resource "aws_iam_role_policy" "sfn_glue" {
  name   = "${var.name_prefix}-pipeline-sfn-glue"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn_glue.json
}

# ---------- EventBridge: the trigger ----------

resource "aws_cloudwatch_event_rule" "new_file" {
  name        = "${var.name_prefix}-new-raw-file"
  description = "New file in the bronze bucket's incoming/ folder"

  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created"]
    detail = {
      bucket = { name = [aws_s3_bucket.this["bronze"].id] }
      object = { key = [{ prefix = "incoming/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.new_file.name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.events.arn
}

# EventBridge may only start our state machine.
data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "events" {
  name               = "${var.name_prefix}-pipeline-events"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}

data "aws_iam_policy_document" "events_start" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.pipeline.arn]
  }
}

resource "aws_iam_role_policy" "events_start" {
  name   = "${var.name_prefix}-pipeline-events-start"
  role   = aws_iam_role.events.id
  policy = data.aws_iam_policy_document.events_start.json
}