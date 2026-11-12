variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "github_repository" {
  description = "owner/repo që lejohet të marrë rolet"
  type        = string
  default     = "remida-egi-klea-s-greentrack/greentrack-gyals"
}

variable "github_sub_prefixes" {
  description = <<-EOT
    Prefikset e claim-it `sub` që pranohen. Repo përdor "immutable subject" (owner@id/repo@id),
    shih GET /repos/{repo}/actions/oidc/customization/sub; formati klasik mbahet për siguri.
  EOT
  type        = list(string)
  default = [
    "repo:remida-egi-klea-s-greentrack@351971781/greentrack-gyals@1439962229",
    "repo:remida-egi-klea-s-greentrack/greentrack-gyals",
  ]
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
