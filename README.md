# MaStR data pipeline

Data product for Marktstammdatenregister (MaStR) extracts covering
Potsdam-Mittelmark (Brandenburg): wind, solar, biomass, and storage.

Orchestration lives in the sister repository `mastr-airflow` (not this repo).

## Architecture

```text
4 CSVs  →  GCS Bronze  →  4 BigQuery Raw tables
                              ↓
                       4 dbt Staging views
                              ↓
                       int_mastr_units (UNION ALL + classification)
                              ↓
                       Gold (dims + fct + mart)
```

| Layer | BigQuery dataset | Objects |
|---|---|---|
| Raw | `mastr_raw` | `raw_mastr_wind`, `raw_mastr_solar`, `raw_mastr_biomass`, `raw_mastr_storage` |
| Staging | `mastr_staging` | `stg_mastr_wind`, `stg_mastr_solar`, `stg_mastr_biomass`, `stg_mastr_storage` (+ seeds) |
| Intermediate | `mastr_intermediate` | `int_mastr_units` |
| Gold | `mastr_marts` | `dim_*`, `fct_mastr_units`, `mart_municipality_capacity` |

Location: `europe-west3`. Shared Staging transform: dbt macro `select_stg_mastr_units`.

Legacy table `mastr_raw.raw_mastr_units` is retained as a backup only; the loader and dbt do not write or read it.

## Prerequisites

- Python 3.12.8 (see `.python-version`)
- [Poetry](https://python-poetry.org/)
- GCP service account with access to the Bronze bucket and BigQuery datasets
- dbt profile `mastr` in `~/.dbt/profiles.yml` (see `dbt/profiles.yml.example`)

```bash
cp .env.sample .env   # fill GCP_PROJECT_ID, GCS_BUCKET, GOOGLE_APPLICATION_CREDENTIALS
poetry install --with dbt
```

## Configuration

| Source | Role |
|---|---|
| `.env` | Required: `GCP_PROJECT_ID`, `GCS_BUCKET`, `GOOGLE_APPLICATION_CREDENTIALS`, `MASTR_RAW_DIR`, `BQ_DATASET`, `BQ_LOCATION` |
| `config/snapshots.json` | Snapshot SHA-256 digests and expected row counts (single source of truth) |
| `config/mastr_headers.json` | Expected German CSV headers |
| `dbt/seeds/` | Reference dims + `seed_snapshot_expectations` (regenerate via Makefile) |

Place local CSVs under `data/raw/<snapshot_date>/` (`wind.csv`, `solar.csv`, `biomass.csv`, `battery.csv`). That folder is gitignored.

## Common commands

```bash
# Python package tests
make test
# or: poetry run pytest -v

# Regenerate seed_snapshot_expectations.csv from config/snapshots.json
make generate-snapshot-seed

# Bronze upload (create-only)
poetry run python -m mastr_data_pipeline ingest-bronze --snapshot-date 2026-11-09

# BigQuery Raw load (validate-then-replace into the four Raw tables)
poetry run python -m mastr_data_pipeline load-raw --snapshot-date 2026-11-09

# dbt (uses Poetry env + ~/.dbt profile `mastr`)
make dbt-parse
make dbt-seed
make dbt-run
make dbt-test
```

## Snapshots and completeness

A `snapshot_date` is complete when all four source files are present in Raw with
row counts matching `config/snapshots.json` / `seed_snapshot_expectations`, and
Staging + Intermediate counts align. Gold municipality reporting uses only the
latest complete snapshot.

Known snapshot `2026-11-09`: 278 + 20 861 + 56 + 11 416 = **32 611** units.

## Documentation

| Doc | Contents |
|---|---|
| `docs/architecture.md` | Layers, datasets, status |
| `docs/data_validation.md` | Source QA and modeling rules |
| `docs/schema.dbml` | Gold star schema |
| `docs/migration_four_raw_tables.md` | Completed unified → split Raw cutover |
