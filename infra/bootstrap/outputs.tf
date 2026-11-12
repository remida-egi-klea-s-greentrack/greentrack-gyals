# Outputs for bootstrap infrastructure
# Use these values to configure backend.hcl for main Terraform

output "state_bucket" {
  description = "S3 bucket name for Terraform state"
  value       = aws_s3_bucket.terraform_state.bucket
}

output "state_bucket_arn" {
  description = "ARN of the S3 state bucket"
  value       = aws_s3_bucket.terraform_state.arn
}

output "aws_region" {
  description = "AWS region of the state bucket"
  value       = var.aws_region
}

output "backend_config" {
  description = "Backend configuration snippet for main Terraform (copy to backend.hcl)"
  value       = <<-EOT
    # Backend configuration for ${var.group_prefix}-${var.project_name}-${var.environment}
    bucket       = "${aws_s3_bucket.terraform_state.bucket}"
    key          = "${var.project_name}/terraform.tfstate"
    region       = "${var.aws_region}"
    encrypt      = true
    use_lockfile = true  # Terraform 1.10+ native S3 locking
  EOT
}
