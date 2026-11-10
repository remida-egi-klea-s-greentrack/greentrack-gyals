# Standalone root for the ML stack, so it can be applied before the app root (infra/) is merged.
# It only wires modules/ml; the same module block can later move into infra/main.tf.
# Variables used: var.region, var.environment, var.name_prefix, var.force_destroy.

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
}
