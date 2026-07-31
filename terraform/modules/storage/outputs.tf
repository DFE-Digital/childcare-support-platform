output "source_data_bucket_id" {
  description = "ID (name) of the source-data S3 bucket for intermediary build data"
  value       = aws_s3_bucket.this["source_data"].bucket
}

output "source_data_bucket_arn" {
  description = "ARN of the source-data S3 bucket"
  value       = aws_s3_bucket.this["source_data"].arn
}

output "provider_data_bucket_id" {
  description = "ID (name) of the provider-data S3 bucket"
  value       = aws_s3_bucket.this["provider_data"].bucket
}

output "provider_data_bucket_arn" {
  description = "ARN of the provider-data S3 bucket"
  value       = aws_s3_bucket.this["provider_data"].arn
}

output "provider_data_oac_id" {
  description = "ID of the CloudFront Origin Access Control for provider-data"
  value       = aws_cloudfront_origin_access_control.provider_data.id
}

output "vite_bucket_id" {
  description = "ID (name) of the vite-build-outputs S3 bucket"
  value       = aws_s3_bucket.this["vite_outputs"].id
}

output "vite_bucket_arn" {
  description = "ARN of the vite-build-outputs S3 bucket"
  value       = aws_s3_bucket.this["vite_outputs"].arn
}

output "oac_id" {
  description = "ID of the CloudFront Origin Access Control for vite-build-outputs"
  value       = aws_cloudfront_origin_access_control.vite.id
}
