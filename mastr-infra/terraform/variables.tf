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
  description = "Existing GCS Bronze bucket name"
  default     = "your-bronze-bucket-name"
}

variable "dbt_service_account_id" {
  type        = string
  description = "Existing service account ID (account_id, not email)"
  default     = "dbt-service-account"
}

variable "dbt_service_account_display_name" {
  type        = string
  description = "Display name for the dbt service account"
  default     = "dbt Service Account"
}

variable "bigquery_datasets" {
  type        = set(string)
  description = "Existing MaStR BigQuery dataset IDs to manage"
  default = [
    "mastr_raw",
    "mastr_staging",
    "mastr_intermediate",
    "mastr_marts",
  ]
}

variable "tfstate_bucket_name" {
  type        = string
  description = "Dedicated GCS bucket for Terraform remote state (create later; not managed here yet)"
  default     = "wagon-mastr-tfstate-anyarlene-2399"
}
