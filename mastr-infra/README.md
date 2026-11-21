# MaStR infrastructure (`mastr-infra`)

Terraform configuration for existing MaStR GCP resources used by:

- `mastr-data-pipeline` (Python ingest + dbt)
- `mastr-airflow` (orchestration)

This stack **adopts** infrastructure that already exists. It must not recreate or destroy the Bronze bucket, BigQuery datasets, or the dbt service account.

## Layout

```text
mastr-infra/
  README.md
  .gitignore
  terraform/
    versions.tf
    providers.tf
    variables.tf
    backend.tf
    storage.tf
    bigquery.tf
    iam.tf
    outputs.tf
    terraform.tfvars.example
```

Le Wagon–style flat files; no modules.

## What Terraform manages

| Resource | Terraform type |
|---|---|
| Bronze bucket `your-bronze-bucket-name` | `google_storage_bucket.bronze` |
| Datasets `mastr_raw`, `mastr_staging`, `mastr_intermediate`, `mastr_marts` | `google_bigquery_dataset.mastr` |
| Service account `dbt-service-account` | `google_service_account.dbt` |
| Project roles `bigquery.jobUser`, `bigquery.dataEditor` | `google_project_iam_member` |
| Bucket roles `storage.objectCreator`, `storage.objectViewer` | `google_storage_bucket_iam_member` |

## What Terraform does **not** manage

- GCS objects (Bronze CSVs)
- BigQuery tables, views, seeds
- Service account keys / `~/.gcp_keys/*.json`
- Dataset ACL entries (see below)
- Non-MaStR service accounts and unrelated project IAM
- Airflow Docker / VM runtime
- The future Terraform state bucket (documented only until created)

## Dataset IAM left unmanaged

Live datasets grant:

- `projectOwners` → OWNER  
- `projectWriters` → WRITER  
- `projectReaders` → READER  
- `dbt-service-account@…` → OWNER  

In the Google provider, the dataset `access` argument is **authoritative**. Defining or clearing it in Terraform can overwrite those entries. Authoritative `google_bigquery_dataset_iam_binding` / `_iam_policy` resources have the same risk for collaborators.

Therefore:

- Datasets use `lifecycle { ignore_changes = [access] }`.
- No `google_bigquery_dataset_iam_*` resources are defined.
- Runtime access remains covered by project `bigquery.dataEditor` + `bigquery.jobUser` and the existing dataset OWNER grant outside Terraform.

## Safety defaults

- Bucket: `force_destroy = false`, `prevent_destroy = true`
- Datasets: `delete_contents_on_destroy = false`, `prevent_destroy = true`
- Service account: `prevent_destroy = true`
- IAM: additive `*_iam_member` only

## Operator identity

Run Terraform as a **human/operator** GCP user (or a dedicated infra SA) with rights to manage the project resources.

Do **not** use `dbt-service-account` as the Terraform operator. That account lacks `storage.buckets.get` and must remain the pipeline/dbt/Airflow runtime identity only.

## Remote state (prepare later — not created in Step 12B)

Intended backend (`terraform/backend.tf`):

- Bucket: `wagon-mastr-tfstate-anyarlene-2399`
- Prefix: `mastr-infra`
- Location: `europe-west3`
- Uniform bucket-level access: enabled
- Versioning: **enabled** (history + recovery)
- Soft delete / retention: optional but recommended
- State locking: provided by the GCS backend
- Access: grant objectAdmin (or tighter custom role) to the four engineers / infra operators only — **not** the dbt runtime SA

Create the state bucket out-of-band (Console or a one-off `gcloud` command) in a later approved step, then `terraform init` with the GCS backend.

Until that bucket exists, do not initialize against the remote backend.

## Import identifiers (for a later approved step)

Do not import until approved. When ready:

```bash
# Bucket
terraform import 'google_storage_bucket.bronze' your-bronze-bucket-name

# Datasets
terraform import 'google_bigquery_dataset.mastr["mastr_raw"]' projects/your-gcp-project-id/datasets/mastr_raw
terraform import 'google_bigquery_dataset.mastr["mastr_staging"]' projects/your-gcp-project-id/datasets/mastr_staging
terraform import 'google_bigquery_dataset.mastr["mastr_intermediate"]' projects/your-gcp-project-id/datasets/mastr_intermediate
terraform import 'google_bigquery_dataset.mastr["mastr_marts"]' projects/your-gcp-project-id/datasets/mastr_marts

# Service account
terraform import 'google_service_account.dbt' \
  projects/your-gcp-project-id/serviceAccounts/dbt-service-account@your-gcp-project-id.iam.gserviceaccount.com

# Project IAM members
terraform import 'google_project_iam_member.dbt_bigquery_job_user' \
  'your-gcp-project-id roles/bigquery.jobUser serviceAccount:dbt-service-account@your-gcp-project-id.iam.gserviceaccount.com'
terraform import 'google_project_iam_member.dbt_bigquery_data_editor' \
  'your-gcp-project-id roles/bigquery.dataEditor serviceAccount:dbt-service-account@your-gcp-project-id.iam.gserviceaccount.com'

# Bucket IAM members
terraform import 'google_storage_bucket_iam_member.dbt_bronze_object_creator' \
  'your-bronze-bucket-name roles/storage.objectCreator serviceAccount:dbt-service-account@your-gcp-project-id.iam.gserviceaccount.com'
terraform import 'google_storage_bucket_iam_member.dbt_bronze_object_viewer' \
  'your-bronze-bucket-name roles/storage.objectViewer serviceAccount:dbt-service-account@your-gcp-project-id.iam.gserviceaccount.com'
```

After import, require an **empty** `terraform plan` before any apply.

## Local setup (after approval)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform init   # only after state bucket exists / backend decision approved
# terraform plan
```

## Separation of concerns

| Layer | Responsibility |
|---|---|
| Terraform (`mastr-infra`) | Bucket, datasets, SA, MaStR-scoped IAM |
| Python | Ingest Bronze + load Raw |
| dbt | Transform + test |
| Airflow | Orchestrate DAG runs |
| Docker | Local Airflow containers |
