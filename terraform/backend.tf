# Remote state backend (GCS).
#
# DO NOT run `terraform init` against this backend until:
#   1. The dedicated state bucket exists (see README).
#   2. Versioning is enabled on that bucket.
#   3. Operator identities (not the dbt SA) have access.
#   4. Step 12C+ import/adoption is approved.
#
# Intended configuration (bucket not created in Step 12B):
#   bucket = var is not interpolated in backend blocks — use the literal name below
#   or pass -backend-config at init time.

terraform {
  backend "gcs" {
    bucket = "wagon-mastr-tfstate-anyarlene-2399"
    prefix = "mastr-infra"
  }
}
