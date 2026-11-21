# MaStR Dashboard (Streamlit PoC)

Proof-of-concept Streamlit dashboard for operational renewable generation and storage capacity across **38 municipalities in Potsdam-Mittelmark** (Brandenburg).

Data is read **read-only** from BigQuery Gold tables in project `your-gcp-project-id`, dataset `mastr_marts`.

## Features

- Overview KPIs (generation MW, storage MWh, installations, municipalities)
- Capacity by energy source (wind / solar / biomass)
- Top 10 municipalities by generation
- Generation vs storage comparison (separate units)
- Filters:
  - Municipality multiselect with **Select all municipalities** (default: all 38)
  - Energy source: All generation sources / Solar / Wind / Biomass (independent of municipality filter)
- Interactive choropleth map fitted to Potsdam-Mittelmark (`krss=12069`), with legend and unselected municipalities greyed out

## Prerequisites

- Python 3.12+
- Poetry
- Local GCP service account with BigQuery read access (reuse existing key)

Default credentials path:

```text
~/.gcp_keys/dbt-service-account.json
```

## Install

```bash
cd /path/to/mastr-project/mastr-dashboard
cp .env.example .env   # optional
poetry install
```

## Launch

```bash
cd /path/to/mastr-project/mastr-dashboard
poetry run streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Tests

```bash
cd /path/to/mastr-project/mastr-dashboard
poetry run pytest -v
```

## Data sources

| Source | Use |
|--------|-----|
| `mastr_marts.mart_municipality_capacity` | Overview KPIs and charts |
| `mastr_marts.dim_municipality` | Municipality attributes (via mart) |
| `mastr_marts.dim_energy_source` / `fct_mastr_units` | Available for source-level queries |
| Geobasis BB OGC API `gem` collection | Municipality polygons (`krss=12069`) |

Join key for the map: Gold `municipality_id` = GeoJSON property `ags`.

## Notes

- This is a local PoC, not a production deployment.
- CDC change fact (`fct_mastr_unit_changes`) is currently empty and not charted.
- Do not commit credentials or `.env` files.
