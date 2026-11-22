# MaStR infrastructure (`mastr-infra`)

Terraform configuration for MaStR GCP resources in a **dedicated project**, used by:

- `mastr-data-pipeline` (Python ingest + dbt)
- `mastr-airflow` (orchestration)

This stack **creates** MaStR infrastructure in that dedicated project. It must
not manage, import, or modify unrelated GCP projects, their resources, or their
credentials.

Copy [`terraform/terraform.tfvars.sample`](terraform/terraform.tfvars.sample) to
`terraform.tfvars` (gitignored) and set placeholders such as `project_id`,
`bronze_bucket_name`, and `tfstate_bucket_name` for your environment.

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
    terraform.tfvars.sample
```

Flat Terraform layout; no modules.

## What Terraform manages

| Resource | Terraform type |
|---|---|
| Bronze GCS bucket (`bronze_bucket_name`) | `google_storage_bucket.bronze` |
| Datasets `mastr_raw`, `mastr_staging`, `mastr_intermediate`, `mastr_marts` | `google_bigquery_dataset.mastr` |
| Dataset role `bigquery.dataEditor` for the runtime SA | `google_bigquery_dataset_iam_member` |
| Bucket roles `storage.objectCreator`, `storage.objectViewer` | `google_storage_bucket_iam_member` |

Product dataset IDs above are the MaStR schema contract. Project id, region,
Bronze bucket name, and runtime service-account id are variables — see
`terraform.tfvars.sample`. The GCS **state** bucket is not a Terraform variable
for the backend; it is supplied at `terraform init` (see Remote state).

## What Terraform does **not** manage

- The existing runtime service account (looked up via data source; default account id `mastr-runtime`)
- Project-level `roles/bigquery.jobUser` on the runtime SA (granted out-of-band)
- Service-account private keys / JSON key files
- GCS objects (Bronze CSVs)
- BigQuery tables, views, seeds
- Dataset ACL `access` blocks (see below)
- The Terraform state bucket (pre-existing; selected at `terraform init` via
  `-backend-config`; not created or managed by this stack)
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

Do **not** use the pipeline runtime service account as the Terraform operator.
That account is the ingest/dbt/Airflow runtime identity only.

Do **not** change the default gcloud project/account casually; pass the dedicated
project via Terraform variables / explicit `--project` flags when verifying.

## Remote state

`terraform/backend.tf` declares a **partial** GCS backend: type `gcs` and
prefix `mastr-infra` only. The state **bucket** is supplied at initialization
with `-backend-config=bucket=...` (or an equivalent local `backend.hcl` /
`*.backend.hcl`, both gitignored). Terraform backends cannot read `var.*`.

`tfstate_bucket_name` in `terraform.tfvars` is **informational** only: it is
echoed as an output and documents which bucket you intend to use. It does
**not** configure the remote backend. Keep that value aligned with the bucket
you pass to `terraform init`.

Expected properties of the **pre-existing** state bucket (not managed by this stack):

- Dedicated to this MaStR project (do not reuse unrelated project backends)
- Prefix: `mastr-infra` (fixed in `backend.tf`)
- Location aligned with the stack region (default `europe-west3`)
- Uniform bucket-level access and versioning enabled
- State locking via the GCS backend
- Access: operators only — **not** the runtime SA

Do not copy or migrate state from unrelated projects. Do not change the prefix
or point init at a different bucket unless you intentionally relocate state.

## Local setup

**New environment** (create the state bucket out-of-band first):

```bash
cd mastr-infra/terraform
cp terraform.tfvars.sample terraform.tfvars
# Edit placeholders: project_id, bronze_bucket_name, tfstate_bucket_name, …
# terraform init -backend-config="bucket=your-tfstate-bucket-name"
# terraform validate
# terraform plan -out=tfplan
# terraform apply tfplan
```

Optional local backend file (gitignored):

```bash
# backend.hcl — do not commit
# bucket = "your-tfstate-bucket-name"
# terraform init -backend-config=backend.hcl
```

**Existing environment** (already using remote state under prefix `mastr-infra`):
keep `terraform.tfvars` unchanged and re-init with the **same** state bucket.
Prefer `-reconfigure` so Terraform updates local backend settings without a
migrate prompt. Do **not** use `-migrate-state` unless you are intentionally
moving state to a new bucket or prefix.

```bash
cd mastr-infra/terraform
# terraform init -reconfigure -backend-config="bucket=your-tfstate-bucket-name"
# terraform plan   # expect no resource changes if vars are unchanged
```

Pipeline and Airflow runtime settings use the same conceptual variables via
component `.env.sample` files (`GCP_PROJECT_ID`, `GCS_BUCKET`, `BQ_DATASET`,
`BQ_LOCATION`).

## Separation of concerns

| Layer | Responsibility |
|---|---|
| Terraform (`mastr-infra`) | Bronze bucket, datasets, dataset/bucket IAM |
| Python | Ingest Bronze + load Raw |
| dbt | Transform + test (including snapshot CDC models) |
| Airflow | Orchestrate manual DAG runs |
| Docker | Local Airflow containers |
| Streamlit dashboard | Read-only Gold exploration (not provisioned here) |
