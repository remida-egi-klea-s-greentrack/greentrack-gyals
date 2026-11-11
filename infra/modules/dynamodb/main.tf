resource "aws_dynamodb_table" "this" {
  for_each     = var.tables
  name         = "${var.name_prefix}-${each.key}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = each.value.hash_key
  range_key    = each.value.range_key

  attribute {
    name = each.value.hash_key
    type = "S"
  }

  dynamic "attribute" {
    for_each = each.value.range_key != null ? [1] : []
    content {
      name = each.value.range_key
      type = "S"
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}