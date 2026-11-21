# MaStR data pipeline

Data product for Marktstammdatenregister (MaStR) extracts covering
Potsdam-Mittelmark (Brandenburg): wind, solar, biomass, and storage.

Orchestration lives in the sibling directory `mastr-airflow` (same monorepo).

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
| Gold | `mastr_marts` | `dim_*`, `fct_mastr_units`, `mart_municipality_capacity`, `fct_mastr_unit_changes` (CDC) |

Location: `europe-west3`. Shared Staging transform: dbt macro `select_stg_mastr_units`.

Legacy table `mastr_raw.raw_mastr_units` is retained as a backup only; the loader and dbt do not write or read it.

## Prerequisites

- Python 3.12.8 (see `.python-version`)
- [Poetry](https://python-poetry.org/)
- Your dedicated GCP project, Bronze bucket, and BigQuery datasets
- A runtime service account with access to that bucket and the MaStR datasets
- Keyless Application Default Credentials (ADC) that can impersonate that runtime service account
- dbt profile `mastr` in `~/.dbt/profiles.yml` (copy from `dbt/profiles.yml.sample`)

```bash
cp .env.sample .env   # set GCP_PROJECT_ID, GCS_BUCKET, MASTR_RAW_DIR, BQ_DATASET, BQ_LOCATION
# Leave GOOGLE_APPLICATION_CREDENTIALS unset (no JSON keyfile).
# Export DBT_IMPERSONATE_SERVICE_ACCOUNT to your runtime SA email when using
# profile-level impersonation (approach B in dbt/profiles.yml.sample).
poetry install --with dbt
```

### Authentication (keyless)

dbt uses `method: oauth` and Application Default Credentials. Configure **your own**
GCP project id and runtime service-account email; do not commit those values.

Pick exactly one approach (see comments in `dbt/profiles.yml.sample`):

1. **Already-impersonated ADC** — create ADC with
   `gcloud auth application-default login --impersonate-service-account=…`,
   then omit `impersonate_service_account` from `~/.dbt/profiles.yml`.
2. **Profile-level impersonation** — create ordinary user ADC with
   `gcloud auth application-default login`, keep
   `impersonate_service_account: "{{ env_var('DBT_IMPERSONATE_SERVICE_ACCOUNT') }}"`
   in the profile, and export that env var.

## Configuration

| Source | Role |
|---|---|
| `.env` | Required: `GCP_PROJECT_ID`, `GCS_BUCKET`, `MASTR_RAW_DIR`, `BQ_DATASET`, `BQ_LOCATION`. Optional for dbt approach B: `DBT_IMPERSONATE_SERVICE_ACCOUNT`. Leave `GOOGLE_APPLICATION_CREDENTIALS` unset for keyless ADC. |
| `dbt/profiles.yml.sample` | Template for `~/.dbt/profiles.yml` (`method: oauth`, dataset `mastr_staging`, location `europe-west3`) |
| `config/snapshots.json` | Snapshot SHA-256, row counts, and `export_scope` (single source of truth) |
| `config/mastr_headers.json` | Expected German CSV headers (64 columns) |
| `dbt/seeds/` | Reference dims + `seed_snapshot_expectations` (regenerate via Makefile) |

Place local CSVs under `data/raw/<snapshot_date>/` (`wind.csv`, `solar.csv`, `biomass.csv`, `battery.csv`). That folder is gitignored.

### Data Contract (required before Bronze)

Local snapshots must pass `validate-snapshot` before upload. `ingest-bronze` runs the same checks automatically.

**Required files (exactly these four CSVs):** `wind.csv`, `solar.csv`, `biomass.csv`, `battery.csv`  
Non-CSV sidecars are ignored; extra `.csv` files fail validation.

**Agreed export filters:**
- Geography: Landkreis **Potsdam-Mittelmark**, Bundesland **Brandenburg**
- Energy carriers: Wind / Solare Strahlungsenergie / Biomasse / Speicher (one carrier per file)
- Operational statuses: prefer **all statuses** in each export (`In Betrieb`, `In Planung`, `Endgültig stillgelegt`, `Vorübergehend stillgelegt` when present)

**`export_scope` (declared metadata — not a CSV column):**
| Value | Meaning |
|---|---|
| `all_statuses` | CDC-eligible; required for new snapshots |
| `legacy_mixed_filters` | Historical exception for `2026-11-09` only |

The CSV alone cannot prove whether all statuses were included; teammates must declare `export_scope` when registering a snapshot.

**Known snapshots:**
| Date | Scope | Rows | Role |
|---|---|---:|---|
| `2026-11-09` | `legacy_mixed_filters` | 32 611 | Preserved historical load (solar/biomass/battery were operational-only) |
| `2026-11-16` | `all_statuses` | 33 643 | **First CDC baseline** |

### Register a new snapshot

1. Export four MaStR CSVs (all statuses, Potsdam-Mittelmark) into `data/raw/YYYY-MM-DD/`.
2. Compute SHA-256 and row counts; add an `all_statuses` entry to `config/snapshots.json`.
3. Run `make generate-snapshot-seed`.
4. Run `poetry run python -m mastr_data_pipeline validate-snapshot --snapshot-date YYYY-MM-DD`.
5. Only then run Bronze / Raw / dbt (or the Airflow DAG).

Failures include missing/extra CSVs, wrong schema/carrier/geography, missing/duplicate IDs, bad decimals/dates, row-count or checksum mismatch, or invalid `export_scope`.

## Common commands

```bash
# Python package tests
make test
# or: poetry run pytest -v

# Regenerate seed_snapshot_expectations.csv from config/snapshots.json
make generate-snapshot-seed

# Data Contract only (no upload)
poetry run python -m mastr_data_pipeline validate-snapshot --snapshot-date 2026-11-16

# Bronze upload (Data Contract then create-only upload)
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

## Documentation

| Doc | Contents |
|---|---|
| `docs/architecture.md` | Layers, datasets, status |
| `docs/data_validation.md` | Source QA and modeling rules |
| `docs/schema.dbml` | Gold star schema |
| `docs/migration_four_raw_tables.md` | Completed unified → split Raw cutover |
