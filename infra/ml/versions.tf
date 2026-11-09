# Terraform, provider and backend settings for the standalone ML root.
# No variables used. Backend values come from <env>.backend.hcl at init time.

terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {}
}
