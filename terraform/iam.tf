# Existing dbt runtime service account and additive MaStR IAM memberships.
# Use google_*_iam_member only (additive). Do not use iam_binding / iam_policy.
# Do not create or manage service account keys.

resource "google_service_account" "dbt" {
  project      = var.project_id
  account_id   = var.dbt_service_account_id
  display_name = var.dbt_service_account_display_name

  lifecycle {
    prevent_destroy = true
  }
}

# Project-level roles observed on the live dbt SA (Step 12A).
resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_project_iam_member" "dbt_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

# Bronze bucket object roles observed on the live dbt SA (Step 12A).
# objectCreator + objectViewer (not objectAdmin); SA cannot storage.buckets.get.
resource "google_storage_bucket_iam_member" "dbt_bronze_object_creator" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_storage_bucket_iam_member" "dbt_bronze_object_viewer" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.dbt.email}"
}

# Dataset-level OWNER for the dbt SA is intentionally NOT managed here.
# See README → "Dataset IAM left unmanaged".
