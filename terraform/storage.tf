# Existing Bronze landing bucket for MaStR CSV snapshots.
# Objects inside the bucket are owned by the Python pipeline, not Terraform.

resource "google_storage_bucket" "bronze" {
  name                        = var.bronze_bucket_name
  location                    = upper(var.region)
  project                     = var.project_id
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "inherited"
  force_destroy               = false

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  lifecycle {
    prevent_destroy = true
  }
}
