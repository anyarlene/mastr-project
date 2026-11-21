# MaStR infrastructure (`mastr-infra`)

Terraform configuration for MaStR GCP resources in the dedicated project
`mastr-project-1126`, used by:

- `mastr-data-pipeline` (Python ingest + dbt)
- `mastr-airflow` (orchestration)

This stack **creates** MaStR infrastructure in the dedicated project. It must
not manage, import, or modify unrelated GCP projects (for example training or
bootcamp projects), their resources, or their credentials.

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

Flat Terraform layout; no modules.

## What Terraform manages

| Resource | Terraform type |
|---|---|
| Bronze bucket `mastr-project-1126-bronze` | `google_storage_bucket.bronze` |
| Datasets `mastr_raw`, `mastr_staging`, `mastr_intermediate`, `mastr_marts` | `google_bigquery_dataset.mastr` |
| Dataset roles `bigquery.dataEditor` for `mastr-runtime` | `google_bigquery_dataset_iam_member` |
| Bucket roles `storage.objectCreator`, `storage.objectViewer` | `google_storage_bucket_iam_member` |

## What Terraform does **not** manage

- The existing runtime service account `mastr-runtime` (looked up via data source)
- Project-level `roles/bigquery.jobUser` on `mastr-runtime` (already granted out-of-band)
- Service-account private keys / JSON key files
- GCS objects (Bronze CSVs)
- BigQuery tables, views, seeds
- Dataset ACL `access` blocks (see below)
- The Terraform state bucket `mastr-project-1126-tfstate` (created out-of-band; preserve its security settings)
- Unrelated GCP project resources or credentials
- Airflow Docker / VM runtime
- Dashboard read-only service account (deferred)

## Dataset IAM

Runtime write access is granted with additive
`google_bigquery_dataset_iam_member` (`roles/bigquery.dataEditor`) on each
MaStR dataset. Do not use authoritative `iam_binding` / `iam_policy`.

Datasets also use `lifecycle { ignore_changes = [access] }` so Terraform does
not overwrite provider-managed special-group ACL entries via the dataset
`access` argument.

Project-wide `roles/bigquery.dataEditor` is intentionally **not** used.

`roles/bigquery.jobUser` remains project-scoped (jobs cannot be dataset-scoped)
and is left to the existing out-of-band grant.

## Safety defaults

- Bucket: `force_destroy = false`, `prevent_destroy = true`,
  `public_access_prevention = "enforced"`
- Datasets: `delete_contents_on_destroy = false`, `prevent_destroy = true`
- IAM: additive `*_iam_member` only
- No Compute Engine, GKE, Cloud Run, Dataproc, Scheduler, or SA keys

## Operator identity

Run Terraform as a **human/operator** GCP user (or a dedicated infra SA) with
rights to manage the project resources.

Do **not** use `mastr-runtime` as the Terraform operator. That account is the
pipeline/dbt/Airflow runtime identity only.

Do **not** change the default gcloud project/account; pass the dedicated
project via Terraform variables / explicit `--project` flags when verifying.

## Remote state

Backend (`terraform/backend.tf`):

- Bucket: `mastr-project-1126-tfstate` (exclusive to this dedicated project)
- Prefix: `mastr-infra`
- Location: `europe-west3`
- Uniform bucket-level access: enabled
- Versioning: enabled
- Soft delete: 7 days (existing bucket setting; not managed here)
- State locking: provided by the GCS backend
- Access: operators only — **not** the runtime SA

This stack does not create or modify the state bucket. Do not copy or migrate
state from unrelated project backends.

## Local setup (after approval)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # if needed
# terraform init    # only after Phase C approval
# terraform validate
# terraform plan -out=tfplan
# terraform apply tfplan   # only after Phase D approval
```

## Separation of concerns

| Layer | Responsibility |
|---|---|
| Terraform (`mastr-infra`) | Bronze bucket, datasets, dataset/bucket IAM |
| Python | Ingest Bronze + load Raw |
| dbt | Transform + test |
| Airflow | Orchestrate DAG runs |
| Docker | Local Airflow containers |
