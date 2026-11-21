# Remote state backend (GCS).
#
# State lives only in the dedicated MaStR project bucket.
# Do not point this backend at any bootcamp / Le Wagon state bucket.
# Do not copy or migrate old Terraform state.

terraform {
  backend "gcs" {
    bucket = "mastr-project-1126-tfstate"
    prefix = "mastr-infra"
  }
}
