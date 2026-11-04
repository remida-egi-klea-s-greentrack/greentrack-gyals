module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = "greentrack"

  tables = {
    consumption = { hash_key = "timestamp" }
    anomalies   = { hash_key = "timestamp" }
  }
}

module "frontend" {
  source      = "./modules/frontend"
  name_prefix = "greentrack"
}
module "api" {
  source      = "./modules/api"
  name_prefix = "greentrack"
}