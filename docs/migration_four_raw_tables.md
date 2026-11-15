# Migration: unified Raw → four Raw tables

**Status:** Complete (Phases 1–2 + obsolete Staging view removed)  
**Live path:** 4 Raw tables → 4 Staging views → `int_mastr_units` → Gold  
**Backup (retained):** `mastr_raw.raw_mastr_units`  
**Active Raw tables:** `raw_mastr_wind`, `raw_mastr_solar`, `raw_mastr_biomass`, `raw_mastr_storage`

## Goals (achieved)

- Route each Bronze CSV to its own Raw table without losing data.
- Combine the four Staging views in Intermediate (`UNION ALL`); no unified Staging model.
- Keep Intermediate → Gold analytics identical (32 611 units, 38 municipalities, same capacity totals).
- Leave `raw_mastr_units` in place as a Raw-layer backup (loader and dbt do not use it).

## Cutover record

| Phase | Action | Outcome |
|---|---|---|
| 1 | Create split Raw tables; backfill from `raw_mastr_units` by `source_file` | 278 / 20 861 / 56 / 11 416; total 32 611 |
| 2 | dbt rebuild against four Raw sources | Staging views + Intermediate + Gold validated; 137 dbt tests passed |
| Cleanup | Drop obsolete BigQuery view `mastr_staging.stg_mastr_units` | Removed; no dependents |

### Optional reload confirmation

```bash
poetry run python -m mastr_data_pipeline load-raw --snapshot-date 2026-11-09
```

Loader writes **only** the four split tables; legacy `raw_mastr_units` is unchanged.

### Analytical parity (validated)

- Combined Staging / `int_mastr_units` / `fct_mastr_units` = 32 611  
- `dim_municipality` / `mart_municipality_capacity` = 38  
- Gold operational totals unchanged vs pre-cutover baseline  
- Completeness selects snapshot `2026-11-09`

## Rollback (historical)

If the split path had failed, options were: git-revert dbt to the unified-Raw Staging wiring, or recreate Staging from `raw_mastr_units`. Those steps are no longer needed for day-to-day operation; prefer restoring from git history if a temporary view is required.

## Remaining decommission (optional)

Only when the backup is no longer required, in a separate approved change: archive or drop `mastr_raw.raw_mastr_units`. Do not drop the four active Raw tables.
