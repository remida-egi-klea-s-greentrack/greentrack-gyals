# Forecast pipeline (Challenge 3 MLOps): Prepare (Gold through Athena) -> Train (built-in XGBoost, spot)
# -> Evaluate (validation window vs seasonal baselines) -> Register in the Model Registry with manual
# approval, only if XGBoost beats the best baseline; otherwise the run fails with a clear message.
# A GitHub Actions workflow starts runs through a dedicated OIDC role.
# Variables used: var.name_prefix, var.xgboost_image, var.github_repository.
# Locals from inference.tf: account_id, region, gold_database, athena_workgroup; data sources for the
# gold and artifacts buckets. Step code: ml/pipeline/steps.py, uploaded below.
# Locals here:
#   pipeline_name, model_group      - names of the pipeline and the Model Package Group
#   code_files                      - Python files the processing jobs need (repo-relative)
#   code_uri, runs_uri              - S3 locations of the step code and of each run's outputs
#   xgboost_hyperparameters         - frozen settings of the validated model (ml/forecasting/xgboost_model.py)
#   job_tags                        - tags on the jobs the pipeline starts (default_tags do not reach them)

locals {
  pipeline_name = "${var.name_prefix}-forecast-pipeline"
  model_group   = "${var.name_prefix}-forecast"
  repo_root     = "${path.module}/../../.."

  code_files = concat(
    ["ml/__init__.py", "ml/inference/__init__.py", "ml/inference/aws.py", "ml/pipeline/__init__.py", "ml/pipeline/steps.py"],
    [for f in fileset(local.repo_root, "ml/forecasting/*.py") : f],
  )
  code_uri = "s3://${aws_s3_bucket.ml.bucket}/pipeline/code/"
  runs_uri = "s3://${aws_s3_bucket.ml.bucket}/pipeline/runs"

  xgboost_hyperparameters = {
    objective        = "reg:squarederror"
    num_round        = "200"
    max_depth        = "4"
    eta              = "0.05"
    subsample        = "0.9"
    colsample_bytree = "0.9"
    tree_method      = "hist"
    seed             = "42"
  }

  job_tags = [{ Key = "Project", Value = "greentrack" }, { Key = "Group", Value = "g2" }]

  # Run outputs: s3://<ml bucket>/pipeline/runs/<execution id>/<step>/<output>
  run_output = { for name in ["train", "hours", "evaluation"] : name => {
    "Std:Join" = { On = "/", Values = [local.runs_uri, { Get = "Execution.PipelineExecutionId" }, name] }
  } }

  processing_input = {
    AppManaged = false
    S3Input = {
      S3DataType             = "S3Prefix"
      S3InputMode            = "File"
      S3DataDistributionType = "FullyReplicated"
      S3CompressionType      = "None"
    }
  }

  processing_job = {
    ProcessingResources = { ClusterConfig = {
      InstanceType   = { Get = "Parameters.ProcessingInstanceType" }
      InstanceCount  = 1
      VolumeSizeInGB = 5
    } }
    RoleArn           = aws_iam_role.sagemaker.arn
    StoppingCondition = { MaxRuntimeInSeconds = 1800 }
    Environment       = { PYTHONPATH = "/opt/ml/processing/input/code" }
    Tags              = local.job_tags
  }

  code_input = merge(local.processing_input, {
    InputName = "code"
    S3Input   = merge(local.processing_input.S3Input, { S3Uri = local.code_uri, LocalPath = "/opt/ml/processing/input/code" })
  })

  pipeline_definition = {
    Version  = "2020-12-01"
    Metadata = {}
    Parameters = [
      { Name = "ProcessingInstanceType", Type = "String", DefaultValue = "ml.t3.medium" },
      { Name = "TrainingInstanceType", Type = "String", DefaultValue = "ml.m5.large" },
    ]
    Steps = [
      {
        Name = "Prepare"
        Type = "Processing"
        Arguments = merge(local.processing_job, {
          AppSpecification = {
            ImageUri            = var.xgboost_image
            ContainerEntrypoint = ["python3", "-m", "ml.pipeline.steps", "prepare"]
          }
          Environment = merge(local.processing_job.Environment, {
            ATHENA_DATABASE    = local.gold_database
            ATHENA_WORKGROUP   = local.athena_workgroup
            AWS_DEFAULT_REGION = local.region
          })
          ProcessingInputs = [local.code_input]
          ProcessingOutputConfig = { Outputs = [for name in ["train", "hours"] : {
            OutputName = name
            AppManaged = false
            S3Output   = { S3Uri = local.run_output[name], LocalPath = "/opt/ml/processing/${name}", S3UploadMode = "EndOfJob" }
          }] }
        })
      },
      {
        Name = "Train"
        Type = "Training"
        Arguments = {
          AlgorithmSpecification = { TrainingImage = var.xgboost_image, TrainingInputMode = "File" }
          RoleArn                = aws_iam_role.sagemaker.arn
          HyperParameters        = local.xgboost_hyperparameters
          InputDataConfig = [{
            ChannelName = "train"
            ContentType = "text/csv"
            DataSource = { S3DataSource = {
              S3DataType             = "S3Prefix"
              S3Uri                  = { Get = "Steps.Prepare.ProcessingOutputConfig.Outputs['train'].S3Output.S3Uri" }
              S3DataDistributionType = "FullyReplicated"
            } }
          }]
          OutputDataConfig = { S3OutputPath = "s3://${aws_s3_bucket.ml.bucket}/pipeline/models" }
          ResourceConfig = {
            InstanceType   = { Get = "Parameters.TrainingInstanceType" }
            InstanceCount  = 1
            VolumeSizeInGB = 5
          }
          # Spot capacity: cheaper; MaxWait covers waiting for capacity plus the run itself.
          EnableManagedSpotTraining = true
          StoppingCondition         = { MaxRuntimeInSeconds = 1800, MaxWaitTimeInSeconds = 3600 }
          Tags                      = local.job_tags
        }
      },
      {
        Name = "Evaluate"
        Type = "Processing"
        Arguments = merge(local.processing_job, {
          AppSpecification = {
            ImageUri            = var.xgboost_image
            ContainerEntrypoint = ["python3", "-m", "ml.pipeline.steps", "evaluate"]
          }
          ProcessingInputs = [
            local.code_input,
            merge(local.processing_input, {
              InputName = "model"
              S3Input = merge(local.processing_input.S3Input, {
                S3Uri     = { Get = "Steps.Train.ModelArtifacts.S3ModelArtifacts" }
                LocalPath = "/opt/ml/processing/model"
              })
            }),
            merge(local.processing_input, {
              InputName = "hours"
              S3Input = merge(local.processing_input.S3Input, {
                S3Uri     = { Get = "Steps.Prepare.ProcessingOutputConfig.Outputs['hours'].S3Output.S3Uri" }
                LocalPath = "/opt/ml/processing/hours"
              })
            }),
          ]
          ProcessingOutputConfig = { Outputs = [{
            OutputName = "evaluation"
            AppManaged = false
            S3Output   = { S3Uri = local.run_output["evaluation"], LocalPath = "/opt/ml/processing/evaluation", S3UploadMode = "EndOfJob" }
          }] }
        })
        PropertyFiles = [{ PropertyFileName = "Evaluation", OutputName = "evaluation", FilePath = "evaluation.json" }]
      },
      {
        Name = "BeatsBaseline"
        Type = "Condition"
        Arguments = {
          Conditions = [{
            Type       = "LessThan"
            LeftValue  = { "Std:JsonGet" = { PropertyFile = { Get = "Steps.Evaluate.PropertyFiles.Evaluation" }, Path = "xgboost_rmse" } }
            RightValue = { "Std:JsonGet" = { PropertyFile = { Get = "Steps.Evaluate.PropertyFiles.Evaluation" }, Path = "baseline_rmse" } }
          }]
          IfSteps = [{
            Name = "Register"
            Type = "RegisterModel"
            Arguments = {
              ModelPackageGroupName = aws_sagemaker_model_package_group.forecast.model_package_group_name
              # The approval step: a person approves the package before it is deployed.
              ModelApprovalStatus = "PendingManualApproval"
              InferenceSpecification = {
                Containers = [{
                  Image        = var.xgboost_image
                  ModelDataUrl = { Get = "Steps.Train.ModelArtifacts.S3ModelArtifacts" }
                }]
                SupportedContentTypes                   = ["text/csv"]
                SupportedResponseMIMETypes              = ["text/csv"]
                SupportedRealtimeInferenceInstanceTypes = ["ml.m5.large"]
                SupportedTransformInstanceTypes         = ["ml.m5.large"]
              }
              ModelMetrics = { ModelQuality = { Statistics = {
                ContentType = "application/json"
                S3Uri = { "Std:Join" = { On = "/", Values = [
                  { Get = "Steps.Evaluate.ProcessingOutputConfig.Outputs['evaluation'].S3Output.S3Uri" },
                  "evaluation.json",
                ] } }
              } } }
            }
          }]
          ElseSteps = [{
            Name      = "NotBetterThanBaseline"
            Type      = "Fail"
            Arguments = { ErrorMessage = "XGBoost validation RMSE is not below the best seasonal naive baseline; nothing registered." }
          }]
        }
      },
    ]
  }
}

resource "aws_s3_object" "pipeline_code" {
  for_each = toset(local.code_files)
  bucket   = aws_s3_bucket.ml.id
  key      = "pipeline/code/${each.value}"
  source   = "${local.repo_root}/${each.value}"
  etag     = filemd5("${local.repo_root}/${each.value}")
}

resource "aws_sagemaker_model_package_group" "forecast" {
  model_package_group_name        = local.model_group
  model_package_group_description = "24-hour XGBoost consumption forecast; packages wait for manual approval"
}

resource "aws_sagemaker_pipeline" "forecast" {
  pipeline_name         = local.pipeline_name
  pipeline_display_name = local.pipeline_name
  pipeline_description  = "Prepare from Gold, train XGBoost, evaluate against baselines, register for approval"
  role_arn              = aws_iam_role.sagemaker.arn
  pipeline_definition   = jsonencode(local.pipeline_definition)

  # Runs read the uploaded code, so upload it before the definition changes.
  depends_on = [aws_s3_object.pipeline_code]
}

# ---------- Permissions of the SageMaker role for pipeline runs ----------

data "aws_iam_policy_document" "pipeline" {
  # The pipeline service (same role) starts and watches the step jobs and registers the model.
  statement {
    sid = "PipelineJobs"
    actions = [
      "sagemaker:CreateProcessingJob", "sagemaker:DescribeProcessingJob", "sagemaker:StopProcessingJob",
      "sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob",
      "sagemaker:AddTags",
    ]
    resources = [
      "arn:aws:sagemaker:${local.region}:${local.account_id}:processing-job/*",
      "arn:aws:sagemaker:${local.region}:${local.account_id}:training-job/*",
    ]
  }

  statement {
    sid     = "RegisterModel"
    actions = ["sagemaker:CreateModelPackage", "sagemaker:DescribeModelPackage", "sagemaker:AddTags"]
    resources = [
      aws_sagemaker_model_package_group.forecast.arn,
      "arn:aws:sagemaker:${local.region}:${local.account_id}:model-package/${local.model_group}/*",
    ]
  }

  statement {
    sid       = "PassOwnRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.sagemaker.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["sagemaker.amazonaws.com"]
    }
  }

  # Prepare step: read-only Athena query of the Gold hourly table.
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

  statement {
    sid       = "GoldTableFiles"
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.gold.arn}/*"]
  }

  statement {
    sid       = "AthenaResultsBucket"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [data.aws_s3_bucket.artifacts.arn]
  }

  statement {
    sid       = "AthenaResultsObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${data.aws_s3_bucket.artifacts.arn}/athena-results/*"]
  }
}

resource "aws_iam_role_policy" "pipeline" {
  name   = "${var.name_prefix}-sagemaker-pipeline"
  role   = aws_iam_role.sagemaker.id
  policy = data.aws_iam_policy_document.pipeline.json
}

# ---------- GitHub Actions trigger ----------

# The account's existing GitHub OIDC provider is only read here, never changed.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Only workflows running on main of this repository.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_pipeline" {
  name               = "${var.name_prefix}-github-ml-pipeline"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

data "aws_iam_policy_document" "github_pipeline" {
  statement {
    sid       = "StartAndWatchPipeline"
    actions   = ["sagemaker:StartPipelineExecution", "sagemaker:DescribePipelineExecution", "sagemaker:ListPipelineExecutionSteps"]
    resources = [aws_sagemaker_pipeline.forecast.arn, "${aws_sagemaker_pipeline.forecast.arn}/execution/*"]
  }
}

resource "aws_iam_role_policy" "github_pipeline" {
  name   = "${var.name_prefix}-github-ml-pipeline"
  role   = aws_iam_role.github_pipeline.id
  policy = data.aws_iam_policy_document.github_pipeline.json
}
