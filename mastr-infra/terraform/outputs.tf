output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "Primary MaStR region"
  value       = var.region
}

output "bronze_bucket_name" {
  description = "MaStR Bronze GCS bucket"
  value       = google_storage_bucket.bronze.name
}

output "bronze_bucket_url" {
  description = "gs:// URL for the Bronze bucket"
  value       = "gs://${google_storage_bucket.bronze.name}"
}

output "bigquery_dataset_ids" {
  description = "Managed MaStR BigQuery dataset IDs"
  value       = sort([for ds in google_bigquery_dataset.mastr : ds.dataset_id])
}

output "runtime_service_account_email" {
  description = "Email of the existing MaStR runtime service account"
  value       = data.google_service_account.runtime.email
}

output "tfstate_bucket_name" {
  description = "Pre-existing remote state bucket name (not managed by this stack)"
  value       = var.tfstate_bucket_name
}
