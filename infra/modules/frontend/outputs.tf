output "bucket_name" {
  description = "S3 bucket that holds the built frontend"
  value       = aws_s3_bucket.site.bucket
}

output "cloudfront_domain" {
  description = "HTTPS address of the dashboard"
  value       = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_url" {
  description = "Full HTTPS URL of the dashboard"
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.site.id
}