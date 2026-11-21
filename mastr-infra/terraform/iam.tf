# Existing MaStR runtime service account and additive IAM memberships.
# Use google_*_iam_member only (additive). Do not use iam_binding / iam_policy.
# Do not create or manage service accounts or service account keys.
#
# Project-level roles/bigquery.jobUser is already granted to mastr-runtime
# outside this stack — do not manage that binding here.

data "google_service_account" "runtime" {
  account_id = var.runtime_service_account_id
  project    = var.project_id
}

# Dataset-scoped data access for raw ingestion and dbt transforms.
resource "google_bigquery_dataset_iam_member" "runtime_data_editor" {
  for_each = google_bigquery_dataset.mastr

  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${data.google_service_account.runtime.email}"
}

# Bronze bucket object roles (not objectAdmin); SA cannot storage.buckets.get.
resource "google_storage_bucket_iam_member" "runtime_bronze_object_creator" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${data.google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runtime_bronze_object_viewer" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_service_account.runtime.email}"
}
