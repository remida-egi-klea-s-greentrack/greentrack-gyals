resource "aws_dynamodb_table" "this" {
  for_each     = var.tables
  name         = "${var.name_prefix}-${each.key}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = each.value.hash_key

  attribute {
    name = each.value.hash_key
    type = "S"
  }
}