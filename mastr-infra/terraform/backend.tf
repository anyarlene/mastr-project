# Remote state backend (GCS) — partial configuration.
#
# The state bucket name is supplied at `terraform init` via
# `-backend-config=bucket=...` or a local `backend.hcl` (gitignored).
# Prefix stays in-repo as the MaStR product contract.
# Do not point this backend at any bootcamp / Le Wagon state bucket.
# Do not copy or migrate old Terraform state.

terraform {
  backend "gcs" {
    prefix = "mastr-infra"
  }
}
