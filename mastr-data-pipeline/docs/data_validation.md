# MaStR source data validation

**Snapshot folder:** `data/raw/2026-11-09/`  
**Validated:** 2026-11-15 (development VM)
**Scope:** read-only inspection of four Marktstammdatenregister CSV extracts

## Source files

| Destination file | Original Windows filename | Size (bytes) | Rows | Columns | SHA-256 |
|---|---|---:|---:|---:|---|
| `wind.csv` | `Stromerzeuger.csv` | 187 726 | 278 | 64 | `a1987b4647c6227138a4062f1c123c05d367a803ff634fb6ca69357d3bc0a192` |
| `solar.csv` | `Stromerzeuger (2).csv` | 13 796 024 | 20 861 | 64 | `3b26e599bfa7f464c046b010ae51c99937eca58c96b3ed9593c0e6dc0b769a96` |
| `biomass.csv` | `Stromerzeuger (3).csv` | 39 060 | 56 | 64 | `2c52fcc0c9b1e317f2047f86627f7a8859bc5fc56df152da30a99d8238fcbb70` |
| `battery.csv` | `Stromerzeuger (1).csv` | 6 951 264 | 11 416 | 64 | `fa1fdf099c05c4fee23a49d14054975225dfe1303660fb339756f5f9ff9803c2` |

**Total units:** 32 611  
**Format:** UTF-8 with BOM (`utf-8-sig`), delimiter `;`, identical 64-column schema across all files  
**Geography:** `Bundesland` = Brandenburg; `Landkreis` = Potsdam-Mittelmark; 38 distinct `Gemeindeschlüssel` (8-digit AGS)

### Expected row counts for snapshot `2026-11-09`

These counts are the expected source-file row counts used for load completeness checks:

| `source_file` | Expected rows |
|---|---:|
| `wind.csv` | 278 |
| `solar.csv` | 20 861 |
| `biomass.csv` | 56 |
| `battery.csv` | 11 416 |

## Integrity checks

| Check | wind | solar | biomass | battery |
|---|---|---|---|---|
| Missing `MaStR-Nr. der Einheit` | 0 | 0 | 0 | 0 |
| Duplicate unit IDs | 0 | 0 | 0 | 0 |
| Full-row duplicates | 0 | 0 | 0 | 0 |
| Cross-file shared unit IDs | — | — | — | **0 across all files** |
| Missing `Gemeindeschlüssel` / `Gemeinde` | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Missing `Bruttoleistung` / `Nettonennleistung` | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Missing `Nutzbare Speicherkapazität in kWh` | 278 (expected) | 20 861 (expected) | 56 (expected) | **0** |
| Missing `MaStR-Nr. der Speichereinheit` | 278 (expected) | 20 861 (expected) | 56 (expected) | **0** |

## Energy carrier and operational status

| File | `Energieträger` | `Betriebs-Status` |
|---|---|---|
| wind | Wind (278) | In Betrieb 220 · In Planung 53 · Endgültig stillgelegt 5 |
| solar | Solare Strahlungsenergie (20 861) | In Betrieb 20 861 |
| biomass | Biomasse (56) | In Betrieb 56 |
| battery | Speicher (11 416) | In Betrieb 11 416 |

`is_operational` in the warehouse is `true` only for `In Betrieb`.

## Storage technology (not all Speicher = battery)

The destination file `battery.csv` contains all rows with `Energieträger = Speicher`. Technology must be taken from `Speichertechnologie`:

| `Speichertechnologie` | Rows | English `energy_source_code` | `energy_source_group` |
|---|---:|---|---|
| Batterie | 11 412 | `battery` | `storage` |
| Wasserstoffspeicher | 4 | `hydrogen_storage` | `storage` |

Unknown or missing storage technology maps to `other_storage` (still `storage`). Generation codes (`wind`, `solar`, `biomass`) come from `Energieträger` only.

## Municipality join readiness

| Overlap | Shared `Gemeindeschlüssel` |
|---|---:|
| solar ∩ battery file | 38 (identical) |
| wind ∩ solar / battery file | 17 |
| biomass ∩ solar / battery file | 21 |
| wind ∩ biomass | 11 |
| Intersection of all four | 11 |
| Union | 38 |

Join key: `Gemeindeschlüssel`. All rows have a non-null 8-digit code.

## ID patterns

- Unit IDs use prefix `SEE` (`MaStR-Nr. der Einheit`).
- Storage registry IDs use prefix `SSE` (`MaStR-Nr. der Speichereinheit`).
- In the Speicher extract, unit ID ≠ storage ID (0 equal pairs in this snapshot).

## Gross vs net power

| File | Rows with gross = net | Rows with gross > net |
|---|---:|---:|
| wind | 278 | 0 |
| solar | 7 689 | 13 172 |
| biomass | 52 | 4 |
| battery (Speicher file) | 9 837 | 1 579 |

**Decision:** municipality comparisons use **net rated power** (`Nettonennleistung der Einheit`).

Business reasoning: net power is the rated power at the grid connection and is comparable across municipalities and technologies. Gross / nameplate (`Bruttoleistung`) is never below net in this extract and is often higher (especially solar), so summing gross would inflate municipality totals. Retain `gross_power_kw` on the fact for audit only; do not use it for headline MW.

### Measure rules

| `energy_source_group` | `generation_power_kw` | `storage_power_kw` | `storage_capacity_kwh` |
|---|---|---|---|
| `generation` | net kW | NULL | NULL |
| `storage` | NULL | net kW | usable kWh |

Keep renewable generation power (kW), storage power (kW), and usable storage energy (kWh) as separate metrics. Battery vs hydrogen storage are distinguished by `energy_source_code`, not by mixing measures.

## Lineage (BigQuery raw load)

Original CSVs in GCS remain unchanged.

Each CSV loads into its own Raw table (`raw_mastr_wind` / `_solar` / `_biomass` /
`_storage`). At load, attach and persist:

| Column | Meaning | Example |
|---|---|---|
| `source_file` | Destination filename loaded | `solar.csv` |
| `snapshot_date` | Snapshot partition (folder date) | `2026-11-09` |
| `ingested_at` | UTC timestamp of the raw load | `2026-11-15T14:00:00Z` |

dbt Staging, Intermediate, and Marts preserve these columns for audit and
completeness checks. Path: **4 Raw tables → 4 Staging views → Intermediate → Gold**.

## Standardization policy

- **GCS / raw:** German headers and values preserved byte-for-byte (plus checksum validation).
- **dbt staging:** English column names and English categorical codes via macro `select_stg_mastr_units`.
- **dbt intermediate + marts:** English-only business classification and measures.
- Staging keeps German audit columns alongside codes: `status_de`, `energy_carrier_de`, `storage_technology_de`.

### Category translation

| German `Energieträger` | (+ `Speichertechnologie`) | `energy_source_code` | `energy_source_group` |
|---|---|---|---|
| Wind | — | `wind` | `generation` |
| Solare Strahlungsenergie | — | `solar` | `generation` |
| Biomasse | — | `biomass` | `generation` |
| Speicher | Batterie | `battery` | `storage` |
| Speicher | Wasserstoffspeicher | `hydrogen_storage` | `storage` |
| Speicher | other / unknown | `other_storage` | `storage` |

| German `Betriebs-Status` | `status_code` | `is_operational` |
|---|---|---|
| In Betrieb | `operational` | `true` |
| In Planung | `planned` | `false` |
| Endgültig stillgelegt | `decommissioned` | `false` |
| Vorübergehend stillgelegt | `temporarily_decommissioned` | `false` |

## Data Contract (local, before Bronze)

Implemented in `mastr_data_pipeline.data_contract` and enforced by
`validate-snapshot` / `ingest-bronze`.

Checks: exactly four required CSVs; UTF-8 (BOM optional); semicolon delimiter;
64 German headers; source-specific `Energieträger`; unique `MaStR-Nr. der Einheit`
within and across files; Landkreis/Bundesland = Potsdam-Mittelmark / Brandenburg;
European decimals and `DD/MM/YYYY` dates where populated; row counts + SHA-256
vs `config/snapshots.json`.

### `export_scope` metadata

Declared in `config/snapshots.json` — **not** a MaStR CSV column. The file contents
cannot prove whether an export included all operational statuses; the teammate who
registers the snapshot must set:

- `all_statuses` — required for new CDC-eligible snapshots (`cdc_baseline: true`)
- `legacy_mixed_filters` — only for historical `2026-11-09`

| Snapshot | Scope | Notes |
|---|---|---|
| `2026-11-09` | `legacy_mixed_filters` | Wind all statuses; solar/biomass/battery operational-only |
| `2026-11-16` | `all_statuses` | First CDC baseline (33 643 rows) |

## Latest complete snapshot

A `snapshot_date` is **complete** only when all of the following hold:

1. All four expected CSV files were successfully loaded into the four Raw tables (`wind.csv`, `solar.csv`, `biomass.csv`, `battery.csv`).
2. Actual loaded row counts match `config/snapshots.json` / `seed_snapshot_expectations`.
3. Raw, Staging, and Intermediate counts agree per `source_file` (see ephemeral model `complete_snapshots`).
4. There are no failed or incomplete loads for that snapshot.

Then:

```text
latest_complete_snapshot_date =
  max(snapshot_date) among complete snapshot_dates
```

Municipality-level capacity reporting must filter to `snapshot_date = latest_complete_snapshot_date` so units are not double-counted across extracts and partial loads are excluded.

## Dimensional model (summary)

Dimensional star schema — see `docs/schema.dbml`:

| Table | Type | Grain |
|---|---|---|
| `dim_municipality` | dimension | one row per `municipality_id` |
| `dim_energy_source` | dimension | one row per energy source code |
| `dim_status` | dimension | one row per status code |
| `fct_mastr_units` | fact | one row per `(snapshot_date, unit_id)` |

- **Primary key (fact):** `(snapshot_date, unit_id)`
- **Foreign keys:** `municipality_id`, `energy_source_id`, `status_id`
- **Snapshot CDC:** `int_mastr_unit_cdc` / `fct_mastr_unit_changes` compare consecutive
  complete `all_statuses` snapshots (starts at `2026-11-16`; Nov 9 excluded).
  DELETE_CANDIDATE is not a confirmed deletion. SCD Type 2 remains deferred.


### dbt tests (implemented)

Singular and generic tests cover:

- Unique `(snapshot_date, unit_id)` on Staging (combined), Intermediate, and `fct_mastr_units`
- Non-null keys and lineage columns on Staging / Intermediate / fact
- Relationship tests from fact (and mart) to the three dimensions
- Capacity / measure-separation rules by `energy_source_group`
- Completeness alignment via `complete_snapshots` and `seed_snapshot_expectations`
- Unique / not-null / accepted-values on dimension keys and codes

## Issues deferred to cleaning / ingestion

1. German decimal commas in power and capacity fields (`6,875`, `4,6`).
2. UTF-8 BOM must be stripped on read (`utf-8-sig`).
3. Wide sparse schema: many technology-specific columns empty by design.
4. Wind includes planned and decommissioned units; operational metrics must filter on `is_operational`.
5. Extreme gross/net ratios on a minority of rows — review during ingestion QA; municipality headlines still use net.

## Conclusion

The four files are consistent, key-complete, and suitable for a unit-grain dimensional model joined on municipality codes. No source-row deduplication is required for this snapshot. Storage must be classified by `Speichertechnologie`. Municipality reporting uses net power, separate storage metrics, and only the latest complete snapshot.
