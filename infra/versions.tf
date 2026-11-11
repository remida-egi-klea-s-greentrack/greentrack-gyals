terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration to be provided via backend config file
  # Run: terraform init -backend-config=backend.hcl
  backend "s3" {
    # Configuration will be provided via backend.hcl or CLI flags
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.default_tags
  }
}