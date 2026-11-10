locals {
  name_prefix = "${var.group_prefix}-${var.project_name}-${var.environment}"
}

module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = local.name_prefix

  tables = {
    consumption = {
      hash_key  = "household_id"
      range_key = "timestamp"
    }
    anomalies = {
      hash_key  = "household_id"
      range_key = "timestamp"
    }
  }
}

module "frontend" {
  source      = "./modules/frontend"
  name_prefix = local.name_prefix
}

module "api" {
  source             = "./modules/api"
  name_prefix        = local.name_prefix
  dynamodb_table_arns = module.dynamodb.table_arns
}