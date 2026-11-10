variable "name_prefix" {
  description = "Prefix for table names"
  type        = string
}

variable "tables" {
  description = "Tables to create, keyed by name"
  type = map(object({
    hash_key  = string
    range_key = optional(string)
  }))
}