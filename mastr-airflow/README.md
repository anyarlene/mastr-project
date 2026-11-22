# MaStR Airflow

Apache Airflow orchestrates the MaStR renewable energy data pipeline using Docker Compose.

The DAG `mastr_snapshot_pipeline` runs the following tasks:

```text
check_local_csvs
    ↓
ingest_bronze
    ↓
load_raw
    ↓
generate_snapshot_seed
    ↓
dbt_seed
    ↓
dbt_run
    ↓
dbt_test
```

## Setup

**Requirements:** Docker Compose, MaStR CSV snapshots, GCP Application Default Credentials (ADC), and a dbt profile.

Run from `mastr-airflow/`:

```bash
cp .env.sample .env
```

Configure `.env` with your GCP project, GCS bucket, BigQuery settings, ADC file path, dbt profile directory, and Airflow credentials.

The dbt profile uses `method: oauth`. The ADC file is mounted read-only into the containers.

## Run Airflow

```bash
docker compose build
docker compose up -d
docker compose ps
```

Airflow UI: http://localhost:8080

## Trigger Pipeline

The DAG is triggered manually using a configured snapshot date.

Example for the current snapshot:

```bash
docker compose exec scheduler poetry run airflow dags trigger \
  mastr_snapshot_pipeline \
  --conf '{"snapshot_date": "2026-11-16"}'
```

The date must exist in `mastr-data-pipeline/config/snapshots.json`, with corresponding CSV files under `mastr-data-pipeline/data/raw/2026-11-16/`.

## Logs and Shutdown

```bash
docker compose logs -f scheduler
```

Stop services:

```bash
docker compose down
```

For data ingestion and dbt transformations, see the [Data Pipeline README](../mastr-data-pipeline/README.md).