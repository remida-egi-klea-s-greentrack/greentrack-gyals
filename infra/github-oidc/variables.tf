variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "github_repository" {
  description = "owner/repo që lejohet të marrë rolet"
  type        = string
  default     = "remida-egi-klea-s-greentrack/greentrack-gyals"
}

variable "name_prefix" {
  description = "Prefiksi i roleve të krijuara këtu"
  type        = string
  default     = "g2-greentrack"
}

variable "state_bucket" {
  description = "Bucket-i i Terraform state (nga bootstrap)"
  type        = string
  default     = "g2-greentrack-tfstate-886565871385"
}

variable "managed_prefixes" {
  description = "Prefikset e burimeve të app stack që deploy role mund t'i menaxhojë (production + e2e)"
  type        = list(string)
  default     = ["g2-greentrack-production", "g2-greentrack-e2e"]
}

variable "assistant_function_name" {
  description = "Lambda e GenAI (e Developer B) ku app stack shton vetëm lejen për /chat"
  type        = string
  default     = "g2-greentrack-assistant"
}
