terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Stack i veçantë me state-in e vet (nuk prek bootstrap apo app stack):
  #   terraform init -backend-config=../backend.hcl -backend-config="key=greentrack/github-oidc.tfstate"
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "GreenTrack"
      ManagedBy = "Terraform"
      Team      = "Group2"
      Purpose   = "github-actions-oidc"
    }
  }
}
