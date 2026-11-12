# Terraform, provider and backend settings for the standalone ML root.
# No variables used. Backend values come from <env>.backend.hcl at init time.

terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    # Zips the inference Lambda code (modules/ml/inference.tf).
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  backend "s3" {}
}
