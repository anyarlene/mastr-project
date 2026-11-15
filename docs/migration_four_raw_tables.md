# Migration: unified Raw → four Raw tables

**Status:** Phase 1 Raw backfill **Done**; Staging/Intermediate/Gold live cutover pending  
**Target path:** 4 Raw tables → 4 Staging views → `int_mastr_units` → Gold  
**Legacy table (keep):** `mastr_raw.raw_mastr_units`  
**Legacy Staging view (keep temporarily):** BigQuery `stg_mastr_units` (rollback only; removed from the local dbt project)  
**New tables:** `raw_mastr_wind`, `raw_mastr_solar`, `raw_mastr_biomass`, `raw_mastr_storage`

## Goals

- Route each Bronze CSV to its own Raw table without losing data.
- Combine the four Staging views in Intermediate (`UNION ALL`); no unified Staging model.
- Keep Intermediate → Gold analytics identical (32 611 units, 38 municipalities, same capacity totals).
- Do **not** drop or overwrite `raw_mastr_units` until the new path is validated.
- Do **not** drop the existing BigQuery `stg_mastr_units` view until rollback is no longer needed.

## Preconditions

1. Repo contains the split loader and dbt sources/views.
2. GCS Bronze snapshot `2026-11-09` intact.
3. Baseline Gold totals captured from the current pipeline (optional but recommended).

## Cutover procedure (live — run only after approval)

### 1. Create empty split tables — Done (Phase 1)

Use the loader’s `ensure_split_raw_tables` (via a dry load path) or create tables with the same schema as `raw_mastr_units` (64 STRING + lineage), partitioned on `snapshot_date`.

### 2. Backfill from legacy Raw — Done (Phase 1)

```sql
-- Repeat pattern for solar / biomass / storage (battery.csv → raw_mastr_storage)
INSERT INTO `PROJECT.mastr_raw.raw_mastr_wind`
SELECT *
FROM `PROJECT.mastr_raw.raw_mastr_units`
WHERE source_file = 'wind.csv';
```

### 3. Compare legacy vs split — Done (Phase 1)

| Check | Expected |
|---|---|
| Row counts by `source_file` | 278 / 20 861 / 56 / 11 416 |
| Total rows | 32 611 |
| Distinct `mastr_nr_der_einheit` | 32 611 |
| Per-file ID sets | Equal to legacy filter |

### 4. Idempotent reload (optional confirmation)

```bash
poetry run python -m mastr_data_pipeline load-raw --snapshot-date 2026-11-09
```

Loader writes **only** the four split tables; legacy `raw_mastr_units` is unchanged.

### 5. dbt rebuild (pending approval)

```bash
cd dbt
poetry run dbt run --select staging intermediate marts
poetry run dbt test
```

Creates/updates the four Staging views and rebuilds Intermediate/Gold from them. Does **not** drop BigQuery `stg_mastr_units`.

### 6. Analytical parity

Confirm:

- Combined Staging / `int_mastr_units` / `fct_mastr_units` = 32 611  
- `dim_municipality` / `mart_municipality_capacity` = 38  
- Mart operational generation/storage totals match pre-cutover baseline  
- Completeness still selects snapshot `2026-11-09`

## Rollback

1. Revert dbt project to the revision that reads legacy Raw / prior Staging wiring (git revert), or temporarily point Intermediate at the retained BigQuery `stg_mastr_units` view if still present.
2. Re-run dbt against the legacy path.
3. Leave the four Raw tables in place (unused) or empty them; do not require dropping them for rollback.
4. Resume loads only after restoring the previous loader revision if needed.

## Decommission (later)

Only after at least one full validated cycle:

1. Stop reading `raw_mastr_units`, then archive/drop it in a separate approved change.
2. Drop BigQuery `stg_mastr_units` once rollback is no longer required.
