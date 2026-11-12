# Data stack: lake buckets, Glue catalog, Glue jobs and Athena.

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

module "data" {
  source      = "../modules/data"
  name_prefix = var.name_prefix
  jobs_dir    = "${path.root}/../../data/jobs"
}