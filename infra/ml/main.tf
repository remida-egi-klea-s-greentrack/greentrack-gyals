# Standalone root for the ML stack, so it can be applied before the app root (infra/) is merged.
# It only wires modules/ml; the same module block can later move into infra/main.tf.
# Variables used: var.region, var.environment, var.name_prefix, var.force_destroy,
# var.enable_endpoints and the four model image/artifact variables.

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "greentrack"
      Group       = "g2"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "ml" {
  source        = "../modules/ml"
  name_prefix   = var.name_prefix
  force_destroy = var.force_destroy

  enable_endpoints   = var.enable_endpoints
  xgboost_image      = var.xgboost_image
  xgboost_model_data = var.xgboost_model_data
  rcf_image          = var.rcf_image
  rcf_model_data     = var.rcf_model_data
}

# Bedrock assistant (Challenge 4); reuses names from the ML module.
module "genai" {
  source      = "../modules/genai"
  name_prefix = var.name_prefix

  gold_database         = module.ml.gold_database
  athena_workgroup      = module.ml.athena_workgroup
  gold_bucket_arn       = module.ml.gold_bucket_arn
  artifacts_bucket_arn  = module.ml.artifacts_bucket_arn
  inference_lambda_arn  = module.ml.inference_lambda_arn
  inference_lambda_name = module.ml.inference_lambda_name
}
