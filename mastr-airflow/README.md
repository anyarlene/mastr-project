# MaStR Airflow

Orchestration-only component for the MaStR data product.
Business logic stays in the sibling directory `mastr-data-pipeline`.

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

1. Monorepo layout: `../mastr-data-pipeline` next to this directory (Compose bind mount).
2. Local snapshot CSVs already present for the date you will run.
3. Docker + Docker Compose on Linux.
4. **Keyless GCP auth** on the host (same approach as the pipeline):
   - Application Default Credentials that already impersonate your runtime service account.
   - dbt profile `mastr` in `~/.dbt/profiles.yml` with `method: oauth` and **no** `keyfile`.
   - Omit `impersonate_service_account` from the profile when ADC is already impersonated
     (avoids double impersonation). See `mastr-data-pipeline/dbt/profiles.yml.sample`.

Do **not** create service-account JSON private keys for this stack.

## Authentication (keyless Docker)

```text
Host MaStR ADC file (already impersonated)
  → bind-mount :ro → /root/.config/gcloud/application_default_credentials.json
  → Python google.auth + dbt method: oauth (GOOGLE_APPLICATION_CREDENTIALS unset)
  → GCS / BigQuery as the runtime service account
```

### MaStR-specific ADC path

Use a dedicated host file for Compose:

```text
~/.config/gcloud/mastr/application_default_credentials.json
```

Set `GCP_ADC_HOST_PATH` in `.env` to the absolute path of that file (see `.env.sample`).

A separate MaStR ADC **file path** only isolates which credentials file Compose
mounts. It does **not** create a different Google user identity, and it does
**not** grant separate refresh-token permissions. The mounted file still
represents the same user credential (and impersonation target) that produced it.

### Do not overwrite an existing default ADC

`gcloud auth application-default login` writes to the **default** ADC location:

```text
~/.config/gcloud/application_default_credentials.json
```

That command may **replace** credentials already stored there. Do **not** run it
if you need to keep an existing default ADC unchanged.

If you already have a suitable already-impersonated ADC for MaStR, **copy** that
file into `~/.config/gcloud/mastr/application_default_credentials.json` and point
`GCP_ADC_HOST_PATH` at the copy. Prefer that over creating a new default ADC.

Compose mounts the host file read-only at the container well-known ADC path.
Access tokens are refreshed in-process by the client libraries. If auth fails
after a long idle period, refresh credentials on the **host** without discarding
unrelated default ADC files you still need, then restart the containers. ADC is
never copied into the image.

## Configuration

```bash
cp .env.sample .env
# Set POSTGRES_PASSWORD, Fernet key, webserver secret, GCP_* placeholders,
# GCP_ADC_HOST_PATH, and DBT_PROFILES_HOST_PATH for your Linux user.
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
| `GCP_ADC_HOST_PATH` | Host MaStR ADC file (typically `~/.config/gcloud/mastr/application_default_credentials.json`) mounted to `/root/.config/gcloud/application_default_credentials.json:ro` |
| `DBT_PROFILES_HOST_PATH` | Host dir mounted to `/opt/dbt:ro` |
| `GCP_PROJECT_ID` / `GCS_BUCKET` / `BQ_DATASET` / `BQ_LOCATION` | Passed into tasks for `get_settings()` |

Leave `GOOGLE_APPLICATION_CREDENTIALS` **unset** in `.env` and Compose.

Inside containers:

| Path | Role |
|---|---|
| `/opt/mastr-data-pipeline` | Mounted pipeline directory (code, `data/raw`, seed write-back) |
| `/opt/venvs/mastr-pipeline` | Image-built dependency venv (GCS, BigQuery, dbt) |
| `/opt/airflow-project/.venv` | Airflow-only Poetry env |
| `/root/.config/gcloud/application_default_credentials.json` | Mounted host MaStR ADC file (read-only) |
| `/opt/dbt` | dbt `profiles.yml` (read-only; `DBT_PROFILES_DIR`) |
| `MASTR_RAW_DIR=/opt/mastr-data-pipeline/data/raw` | Snapshot CSV root |

Pipeline dependency pins live in `container/pipeline-requirements.txt`
(generated from the pipeline `poetry.lock`). Regenerate when pipeline deps change.

## Start / stop

```bash
cd /path/to/mastr-project/mastr-airflow
docker compose build
docker compose up -d
docker compose ps
docker compose down
```

UI: [http://localhost:8080](http://localhost:8080) (admin user from `.env`).

Validate Compose interpolation without starting services:

```bash
make compose-config
```

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
| ADC / auth errors | MaStR ADC **file** exists at `GCP_ADC_HOST_PATH`; leave `GOOGLE_APPLICATION_CREDENTIALS` unset; do not overwrite unrelated default ADC when refreshing |
| dbt profile not found | `DBT_PROFILES_HOST_PATH` mounts a dir containing `profiles.yml`; `DBT_PROFILES_DIR=/opt/dbt` |
| Module not found for `mastr_data_pipeline` | Sibling mount + image pipeline venv present |
| Seed file not updated on host | Pipeline mount must be writable (default bind mount) |

## Teammate setup

1. Work from the monorepo; Compose mounts `../mastr-data-pipeline` next to this directory.
2. Copy `.env.sample` → `.env` and set **your** absolute paths for the MaStR ADC file and dbt profiles.
3. Set `GCP_PROJECT_ID` and `GCS_BUCKET` to **your** dedicated project resources (placeholders in the sample).
4. Place an already-impersonated ADC at `~/.config/gcloud/mastr/application_default_credentials.json` (copy from a suitable existing ADC if needed; do not overwrite an unrelated default ADC). Ensure `~/.dbt/profiles.yml` has oauth `mastr` without profile-level impersonation.
5. Do **not** mount `~/.gcp_keys` or set a JSON key path.
6. Do **not** mount or reuse a host Poetry `.venv`.
7. `make compose-config`, then build and start Compose; trigger manually with your `snapshot_date`.

## Design notes

- Airflow does not import pipeline Python packages into its own env.
- Tasks use `scripts/run_pipeline.sh`, which mirrors Makefile/CLI entrypoints.
- Python ingestion and dbt share the same mounted ADC identity.
- Idempotent reruns rely on existing Bronze create-only behaviour and Raw validate-then-replace.
- Legacy `raw_mastr_units` is never targeted by the loader.
