# MaStR BigQuery datasets.
# Tables, views and seeds are created by Python (Raw) and dbt (Staging+),
# and must stay outside Terraform.

resource "google_bigquery_dataset" "mastr" {
  for_each = var.bigquery_datasets

  dataset_id                 = each.value
  project                    = var.project_id
  location                   = var.region
  delete_contents_on_destroy = false
  max_time_travel_hours      = 168

  # Dataset `access` is authoritative in the Google provider. Leave access
  # unmanaged here; grant runtime access via additive dataset IAM members.
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [access]
  }
}
