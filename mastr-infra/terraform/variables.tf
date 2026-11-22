variable "project_id" {
  type        = string
  description = "GCP project ID that hosts MaStR infrastructure"
}

variable "region" {
  type        = string
  description = "Primary GCP region for MaStR resources"
  default     = "europe-west3"
}

variable "bronze_bucket_name" {
  type        = string
  description = "GCS Bronze bucket name for MaStR CSV snapshots"
}

variable "runtime_service_account_id" {
  type        = string
  description = "Existing runtime service account ID (account_id, not email)"
  default     = "mastr-runtime"
}

variable "bigquery_datasets" {
  type        = set(string)
  description = "MaStR BigQuery dataset IDs to create"
  default = [
    "mastr_raw",
    "mastr_staging",
    "mastr_intermediate",
    "mastr_marts",
  ]
}

variable "tfstate_bucket_name" {
  type        = string
  description = "Pre-existing GCS bucket for Terraform remote state (not managed by this stack)"
}
