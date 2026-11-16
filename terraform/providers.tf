# Provider configuration.
# Use a human/operator GCP identity with admin rights to manage infra.
# Do NOT use the dbt-service-account runtime key as the Terraform operator.

provider "google" {
  project = var.project_id
  region  = var.region
}
