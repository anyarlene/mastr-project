# MaStR project

Monorepo for the MaStR renewable energy data product covering Potsdam-Mittelmark (Brandenburg).

## Components

| Directory | Role |
|---|---|
| `mastr-data-pipeline` | Python ingestion, GCS Bronze, BigQuery Raw, dbt transforms and tests |
| `mastr-airflow` | Airflow orchestration (Docker Compose, LocalExecutor) |
| `mastr-infra` | Terraform for existing GCP infrastructure and IAM |
| `mastr-dashboard` | Streamlit dashboard and municipality map |

Each component keeps its own Poetry environment, documentation and Makefile. Orchestration mounts the pipeline as a sibling directory; credentials and dbt profiles remain outside this repository under the operator home directory.
