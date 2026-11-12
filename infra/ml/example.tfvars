# Example values; copy to <env>.tfvars.
# Variables: region, name_prefix, environment, force_destroy (see variables.tf).

region        = "eu-central-1"
name_prefix   = "g2-greentrack"
environment   = "datamax"
force_destroy = false

# Inference. Images: eu-central-1 built-in algorithms (same as training).
# Model URIs: outputs of the training jobs (aws sagemaker describe-training-job ... ModelArtifacts).
enable_endpoints   = false
xgboost_image      = "492215442770.dkr.ecr.eu-central-1.amazonaws.com/sagemaker-xgboost:3.0-5"
xgboost_model_data = "s3://<ml-bucket>/xgboost/models/<training-job>/output/model.tar.gz"
rcf_image          = "664544806723.dkr.ecr.eu-central-1.amazonaws.com/randomcutforest:1"
rcf_model_data     = "s3://<ml-bucket>/rcf/models/<training-job>/output/model.tar.gz"
