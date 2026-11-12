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
    
    # ML Integration: Tabela per forecast results nga g2-greentrack-ml-inference Lambda
    # Partition key: household_id (identifier i household)
    # Sort key: timestamp (koha e prediction)
    # Mbushet nga ML loader script me predictions 24-orëshe
    forecasts = {
      hash_key  = "household_id"
      range_key = "timestamp"
    }
    
    # ML Integration: Tabela per anomaly detections nga 2 detectors (log-MAD dhe RCF)
    # Partition key: household_id (identifier i household)
    # Sort key: timestamp_detector (format: "2010-01-24T17:00:00#rcf_raw_24")
    #   - Composite key që kombinon timestamp dhe detector name
    #   - Lejon që log-MAD dhe RCF të ruajnë detections në të njëjtën orë pa u overwrite
    #   - Format examples: "2010-01-24T17:00:00#log_mad" ose "2010-01-24T17:00:00#rcf_raw_24"
    # Mbushet nga ML loader script me anomaly scores dhe severities
    anomalies = {
      hash_key  = "household_id"
      range_key = "timestamp_detector"
    }
  }
}

module "frontend" {
  source      = "./modules/frontend"
  name_prefix = local.name_prefix
}

module "api" {
  source              = "./modules/api"
  name_prefix         = local.name_prefix
  dynamodb_table_arns = module.dynamodb.table_arns
}