# MaStR Data Validation

Data-quality checks and modelling rules for the MaStR renewable energy pipeline.

## Source Data

The pipeline processes four CSV files:

| File | Energy source |
|---|---|
| `wind.csv` | Wind |
| `solar.csv` | Solar |
| `biomass.csv` | Biomass |
| `battery.csv` | Battery and hydrogen storage |

**Current snapshot:** `2026-11-16` — 33,643 installations across 38 municipalities in Potsdam-Mittelmark.

## Data Contract

Python validates each snapshot before ingestion into Google Cloud Storage.

Validation includes:

- Required CSV files and 64-column schema
- UTF-8 encoding and semicolon delimiter
- Correct energy source and geographic scope
- Unique, non-null MaStR installation IDs
- Valid dates and decimal values
- Row counts and SHA-256 checksums against `config/snapshots.json`

## Data Modelling Rules

| Rule | Implementation |
|---|---|
| Municipality identifier | 8-digit `Gemeindeschlüssel` (AGS) |
| Generation capacity | Net rated power (kW) |
| Storage power | Net rated power (kW) |
| Storage energy | Usable capacity (kWh) |
| Operational installations | `Betriebs-Status = In Betrieb` |
| Storage classification | `Speichertechnologie` distinguishes battery and hydrogen |
| Standardization | German source fields mapped to English in dbt Staging |

Generation power, storage power, and storage energy are maintained as separate metrics.

## Data Quality Tests

dbt tests verify:

- Unique and non-null identifiers
- Relationships between fact and dimension tables
- Valid energy-source and operational-status values
- Capacity and measurement rules
- Snapshot completeness and row-count consistency

Municipality reporting uses the **latest complete snapshot**.

## Snapshot Change Detection

The implemented CDC models compare consecutive complete snapshots with `export_scope = all_statuses`.

- `int_mastr_unit_cdc` identifies changes.
- `fct_mastr_unit_changes` stores detected change events.

The `2026-11-16` snapshot is the first eligible CDC baseline.

## Run Validation

From `mastr-data-pipeline/`:

```bash
poetry run python -m mastr_data_pipeline validate-snapshot --snapshot-date 2026-11-16
```

For pipeline execution, see the [Data Pipeline README](../README.md).