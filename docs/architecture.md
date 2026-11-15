# MaStR pipeline architecture

Minimal, reproducible architecture for Marktstammdatenregister (MaStR) extracts
covering Potsdam-Mittelmark (Brandenburg): wind, solar, biomass, and storage.

Follows Le Wagon Data Engineering layering:

`raw → staging → intermediate → marts`

Orchestration lives in a **separate** repository (`mastr-airflow`).

Related docs:

- `docs/data_validation.md` — source validation and modeling decisions
- `docs/schema.dbml` — star schema ERD
- `docs/migration_four_raw_tables.md` — completed unified → four Raw tables cutover

---

## Status legend

| Marker | Meaning |
|---|---|
| **Done** | Present in the repo and executed on the VM / GCP |
| **Planned** | Agreed design; not implemented yet |
| **Unresolved** | Intentionally open; not part of the current build |

---

## High-level data flow

```mermaid
flowchart TB
  DL["New MaStR exports<br/>Unresolved: automated download"]
  CSV["MaStR CSV snapshots<br/>data/raw/YYYY-MM-DD/<br/>Done"]

  AF["mastr-airflow DAGs<br/>Planned"]

  PY["Python ingestion<br/>mastr_data_pipeline/<br/>Done"]
  GCS["GCS Bronze<br/>your-bronze-bucket-name<br/>Done"]

  BQRaw["BigQuery Raw (4 tables)<br/>raw_mastr_wind/solar/biomass/storage<br/>Done"]

  STG["dbt Staging (4 views)<br/>stg_mastr_wind/solar/biomass/storage<br/>Done"]
  INT["dbt Intermediate<br/>int_mastr_units (UNION ALL Staging)<br/>Done"]
  MART["dbt Marts<br/>dims + fct + mart_municipality_capacity<br/>Done"]

  DL -.->|"manual until automated"| CSV
  AF -->|"1. trigger Python ingestion"| PY
  CSV --> PY
  PY -->|"2. upload raw CSVs unchanged"| GCS
  AF -->|"3. load GCS → BigQuery Raw"| BQRaw
  GCS --> BQRaw
  AF -->|"4. dbt run / test"| STG
  BQRaw --> STG
  STG --> INT
  INT --> MART
```

**Airflow responsibilities (planned):** orchestrate Python ingestion to GCS Bronze, BigQuery Raw loading, dbt transformations (staging → intermediate → marts), and data quality tests.

**Unresolved:** automated downloading of new MaStR exports. Until that exists, snapshots are supplied manually under `data/raw/<snapshot_date>/` and mirrored to GCS by ingestion.

---

## Repository responsibilities

| Repository | Role | Owns |
|---|---|---|
| `mastr-data-pipeline` | Data product | CSV snapshots (gitignored), Python ingestion package, dbt models/tests/seeds, data docs |
| `mastr-airflow` | Orchestration only | DAGs that trigger ingestion, BigQuery loads, dbt, and tests; `package-mode = false` |

Airflow does **not** own transformation SQL. dbt does **not** schedule itself.

---

## Layer purposes and materialization

| Layer | Purpose | Materialization | Status |
|---|---|---|---|
| **GCS Bronze** | Immutable original MaStR CSV bytes, path-labeled by `snapshot_date` | GCS objects | **Done** (snapshot `2026-11-09` uploaded) |
| **BigQuery Raw** (4 tables) | One table per CSV: `raw_mastr_wind` / `_solar` / `_biomass` / `_storage`; German STRING + lineage. Backup: `raw_mastr_units` (not written by the loader) | **Tables** (partition by `snapshot_date`) | **Done** |
| **dbt Staging** | Four source views; shared DE→EN macro `select_stg_mastr_units` | **Views** in `mastr_staging` | **Done** |
| **dbt Intermediate** | `UNION ALL` of the four Staging views, then energy-source classification, `is_operational`, separate capacity measures | **View** in `mastr_intermediate` | **Done** |
| **dbt Marts** | Star schema + municipality reporting for BI | **Tables** in `mastr_marts` | **Done** |

Le Wagon practice: keep staging and intermediate as views; materialize marts for stable reporting.

Datasets (all `europe-west3`): `mastr_raw`, `mastr_staging`, `mastr_intermediate`, `mastr_marts`.

---

## Architecture stages

### 1. MaStR CSV → Python ingestion → GCS Bronze

| Item | Status | Notes |
|---|---|---|
| Local snapshot `data/raw/2026-11-09/` | **Done** | Four CSVs validated (see `docs/data_validation.md`) |
| Python Bronze ingestion package + tests | **Done** | CLI: `poetry run python -m mastr_data_pipeline ingest-bronze --snapshot-date …` |
| GCS bucket `your-bronze-bucket-name` | **Done** | `europe-west3`; objects under `bronze/mastr/snapshot_date=…/` |
| Automated MaStR export download | **Unresolved** | Separate from upload |

GCS Bronze objects stay immutable. No cleaning in place on the objects.

### 2. GCS Bronze → BigQuery Raw (four tables)

| Item | Status | Notes |
|---|---|---|
| Dataset `mastr_raw` in `europe-west3` | **Done** | Physical Raw layer |
| Split tables | **Done** | `raw_mastr_wind` / `_solar` / `_biomass` / `_storage` (32 611 rows for `2026-11-09`) |
| Legacy `raw_mastr_units` | **Done (backup)** | Unified archive; loader and dbt do not use it |
| Lineage at load | **Done** | `source_file`, `snapshot_date`, `ingested_at` |
| Idempotent reload | **Done** | Per-table validate-then-atomic-replace for that `snapshot_date` |

See `docs/migration_four_raw_tables.md` for the completed cutover record.

### 3. dbt Staging → Intermediate → Marts

#### Staging (views) — Done

- `stg_mastr_wind` / `_solar` / `_biomass` / `_storage` from the four Raw tables
- Shared macro `select_stg_mastr_units` for DE→EN mapping and casts
- No unified Staging model; Intermediate combines the four views

#### Intermediate (views) — Done

Reusable business logic **before** the star schema (`int_mastr_units`):

- `UNION ALL` of the four Staging views
- Classify energy source: generation vs storage; battery vs hydrogen vs other via storage technology codes
- Derive `is_operational` from status
- Build separate measures: `generation_power_kw`, `storage_power_kw`, `storage_capacity_kwh`

#### Marts (tables) — Done

| Model | Role |
|---|---|
| `dim_municipality` | One row per municipality |
| `dim_energy_source` | English codes + `energy_source_group` (from seed) |
| `dim_status` | English status + `is_operational` (from seed) |
| `fct_mastr_units` | Grain `(snapshot_date, unit_id)`; FKs to the three dims |
| `mart_municipality_capacity` | Municipality-level analytical reporting |
| `complete_snapshots` | Ephemeral completeness helper (not a table) |

Seeds (land in `mastr_staging`): `seed_energy_sources`, `seed_statuses`, `seed_snapshot_expectations`.

**Measure policy:** municipality headlines use **net** power; keep generation kW, storage kW, and storage kWh separate; `gross_power_kw` is audit-only. Mart uses only the latest complete snapshot.

### 4. Airflow orchestration (`mastr-airflow`)

| Item | Status | Notes |
|---|---|---|
| Repo scaffold | **Done** | `dags/`, `scripts/`, `tests/`, Poetry `package-mode = false` |
| DAGs | **Planned** | Python ingest → BigQuery Raw load → dbt run → dbt test |

### 5. Data quality, completeness, future CDC / SCD2

| Item | Status | Notes |
|---|---|---|
| Documented source QA | **Done** | Checksums, ID uniqueness, join readiness |
| Raw load validation | **Done** | Expected counts from `config/snapshots.json` |
| dbt tests | **Done** | Unique keys, not-null, relationships, capacity rules, completeness |
| SCD Type 2 / CDC via dbt snapshots | **Planned (design only)** | Hooks in `schema.dbml`; not built yet |

#### Latest complete snapshot

A `snapshot_date` is complete only when:

1. All four expected CSV files loaded successfully into Raw (`wind.csv`, `solar.csv`, `biomass.csv`, `battery.csv`).
2. Actual loaded row counts match the **expected counts for that snapshot** (`config/snapshots.json` / `seed_snapshot_expectations`).
3. Raw, Staging, and Intermediate counts agree per `source_file`.

For snapshot `2026-11-09` the expected counts are 278 / 20 861 / 56 / 11 416. Future snapshots will have their own expected counts.

```text
latest_complete_snapshot_date =
  max(snapshot_date) among complete snapshot_dates
```

`mart_municipality_capacity` filters to that date so historical extracts are not double-counted.

---

## Implemented vs planned

| Done | Planned | Unresolved |
|---|---|---|
| Two-repo scaffold + docs | Airflow DAGs | Automated MaStR export download |
| Local CSV snapshot `2026-11-09` | SCD Type 2 / CDC (dbt snapshots) | |
| Python → GCS Bronze + BigQuery Raw (4 tables) | | |
| dbt Staging (4 views), Intermediate, Marts + tests | | |
| Completeness via seeds + `complete_snapshots` | | |

---

## What is explicitly out of scope for v1

- Implementing SCD Type 2 / CDC (design only)
- Mixing generation kW, storage kW, and storage kWh into one metric
- Treating all `Speicher` rows as batteries
- Putting dbt models or business SQL inside `mastr-airflow`
- Mutating CSV objects after landing in GCS
- Assuming every new MaStR export is downloaded automatically

---

## Reproducibility checklist (Le Wagon-oriented)

1. Pin Python via `.python-version` / Poetry in `mastr-data-pipeline`.
2. Keep raw extracts under `data/raw/<snapshot_date>/` locally (gitignored) and mirror them immutably in GCS via ingestion.
3. Record SHA-256 and **snapshot-specific** expected row counts in `config/snapshots.json` (and regenerate the seed) before promoting a snapshot.
4. Load Raw idempotently (validate then replace per `snapshot_date`); promote only **complete** snapshots to municipality reporting.
5. Transform with dbt (`staging → intermediate → marts`); orchestrate ingest, BigQuery load, dbt run, and tests with Airflow in the sister repo when DAGs exist.
