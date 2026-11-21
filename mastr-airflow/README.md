# MaStR Airflow

Orchestration-only repository for the MaStR data product.
Business logic stays in the sibling repo `mastr-data-pipeline`.

## Architecture

```text
mastr-airflow (Compose: postgres + scheduler + webserver, LocalExecutor)
        │
        │  Bash/Python tasks call scripts/run_pipeline.sh
        ▼
Isolated pipeline venv in the image   (/opt/venvs/mastr-pipeline)
        │
        │  PYTHONPATH + mounted source (no host .venv)
        ▼
mastr-data-pipeline CLI / dbt (mounted at /opt/mastr-data-pipeline)
```

DAG `mastr_snapshot_pipeline` (manual trigger only):

```text
check_local_csvs
  → ingest_bronze
  → load_raw
  → generate_snapshot_seed
  → dbt_seed
  → dbt_run
  → dbt_test
```

- `schedule=None`, `max_active_runs=1`
- Parameter: `snapshot_date` (must exist in `config/snapshots.json` and on disk)
- No automatic MaStR CSV download — place files under `data/raw/<snapshot_date>/`

## Prerequisites

1. Sibling checkout: `../mastr-data-pipeline` next to this repo.
2. Local snapshot CSVs already present for the date you will run.
3. GCP service-account key under `~/.gcp_keys/` (read-only mount).
4. dbt profile `mastr` in `~/.dbt/profiles.yml` with `keyfile` pointing at that key path.
5. Docker + Docker Compose on the VM.

## Configuration

```bash
cp .env.sample .env
# Fill POSTGRES_PASSWORD, Fernet key, webserver secret, GCP_* and host paths.
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | Airflow metadata DB |
| `AIRFLOW__CORE__FERNET_KEY` | Airflow connection encryption |
| `AIRFLOW__WEBSERVER__SECRET_KEY` | UI sessions |
| `GCP_KEYS_HOST_PATH` | Host dir mounted to `/home/YOUR_USER/.gcp_keys:ro` |
| `DBT_PROFILES_HOST_PATH` | Host dir mounted to `/home/YOUR_USER/.dbt:ro` |
| `GCP_PROJECT_ID` / `GCS_BUCKET` / `BQ_DATASET` / `BQ_LOCATION` | Passed into tasks for `get_settings()` |

Inside containers:

| Path | Role |
|---|---|
| `/opt/mastr-data-pipeline` | Mounted sibling repo (code, `data/raw`, seed write-back) |
| `/opt/venvs/mastr-pipeline` | Image-built dependency venv (GCS, BigQuery, dbt) |
| `/opt/airflow-project/.venv` | Airflow-only Poetry env |
| `/home/YOUR_USER/.gcp_keys` | Credentials (read-only; same path as host profiles) |
| `/home/YOUR_USER/.dbt` | dbt `profiles.yml` (read-only) |
| `MASTR_RAW_DIR=/opt/mastr-data-pipeline/data/raw` | Snapshot CSV root |

Pipeline dependency pins live in `container/pipeline-requirements.txt`
(generated from the pipeline `poetry.lock`). Regenerate when pipeline deps change.

## Start / stop

```bash
cd ~/code/anyarlene/mastr-airflow
docker compose build
docker compose up -d
docker compose ps
docker compose down
```

UI: [http://localhost:8080](http://localhost:8080) (default admin user from `.env`).

## Trigger the DAG (`2026-11-09`)

**UI:** Trigger DAG → Configuration JSON:

```json
{"snapshot_date": "2026-11-09"}
```

Or set the DAG param `snapshot_date` in the trigger form.

**CLI (after Compose is up):**

```bash
docker compose exec scheduler poetry run airflow dags trigger \
  mastr_snapshot_pipeline \
  --conf '{"snapshot_date": "2026-11-09"}'
```

## Logs and troubleshooting

```bash
# Service logs
docker compose logs -f scheduler
docker compose logs -f webserver

# Task logs (UI: Grid → task → Log) or on disk:
ls logs/dag_id=mastr_snapshot_pipeline/
```

| Symptom | Check |
|---|---|
| `snapshot_date … not present in snapshots.json` | Add the date to pipeline `config/snapshots.json` first |
| Missing CSVs | Files under `mastr-data-pipeline/data/raw/<date>/` |
| dbt auth / keyfile errors | Mount paths match `profiles.yml` `keyfile`; mounts are `:ro` |
| Module not found for `mastr_data_pipeline` | Sibling mount + image pipeline venv present |
| Seed file not updated on host | Pipeline mount must be writable (default bind mount) |

## Teammate setup

1. Clone both repos as siblings under the same parent directory.
2. Copy `.env.sample` → `.env` and set your user paths for keys/profiles.
3. Ensure `~/.dbt/profiles.yml` contains the `mastr` profile (see pipeline `dbt/profiles.yml.example`).
4. Do **not** mount or reuse a host Poetry `.venv`.
5. Build and start Compose as above; trigger manually with your `snapshot_date`.

## Design notes

- Airflow does not import pipeline Python packages into its own env.
- Tasks use `scripts/run_pipeline.sh`, which mirrors Makefile/CLI entrypoints.
- Idempotent reruns rely on existing Bronze create-only behaviour and Raw validate-then-replace.
- Legacy `raw_mastr_units` is never targeted by the loader.
