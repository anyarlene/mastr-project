# MaStR Infrastructure

Terraform manages the Google Cloud infrastructure for the MaStR renewable energy data pipeline.

## Infrastructure

| Resource | Purpose |
|---|---|
| Google Cloud Storage | Bronze bucket for MaStR CSV snapshots |
| BigQuery | `mastr_raw`, `mastr_staging`, `mastr_intermediate`, `mastr_marts` datasets |
| IAM | Runtime service account permissions for GCS and BigQuery |

Infrastructure is provisioned in a dedicated GCP project using Terraform.

## Setup

**Requirements:** Terraform, GCP access, and an existing GCS bucket for Terraform remote state.

From `mastr-infra/terraform/`:

```bash
cp terraform.tfvars.sample terraform.tfvars
```

Configure `terraform.tfvars` with your GCP project, Bronze bucket, runtime service account, and Terraform state bucket.

## Terraform Commands

Initialize Terraform using the existing state bucket:

```bash
terraform init -backend-config="bucket=YOUR_TFSTATE_BUCKET"
```

Validate and review:

```bash
terraform validate
terraform plan -out=tfplan
```

Apply the reviewed plan:

```bash
terraform apply tfplan
```

For an existing environment, reuse the same state bucket and configuration. Review the plan before applying changes.

## Project Components

- [Data Pipeline](../mastr-data-pipeline/README.md)
- [Airflow](../mastr-airflow/README.md)
- [Dashboard](../mastr-dashboard/README.md)