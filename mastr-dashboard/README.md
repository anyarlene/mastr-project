# MaStR Dashboard (Streamlit visualization)

Streamlit visualization component for operational renewable generation and storage capacity across **38 municipalities in Potsdam-Mittelmark** (Brandenburg).

Data is read **read-only** from BigQuery Gold tables (dataset `mastr_marts` by default). The UI requires a live BigQuery project configured via `GCP_PROJECT_ID` and `BQ_LOCATION` in `.env` (see `.env.sample`). Optional: `BQ_MARTS_DATASET` to override the Gold dataset name.

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
- Keyless GCP Application Default Credentials (ADC) with BigQuery read access to `mastr_marts`

### Authentication (ADC)

Prefer the MaStR-specific ADC file:

```text
~/.config/gcloud/mastr/application_default_credentials.json
```

In `.env` (see `.env.sample`), set:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/home/YOUR_USER/.config/gcloud/mastr/application_default_credentials.json
GCP_PROJECT_ID=your-gcp-project-id
BQ_LOCATION=europe-west3
BQ_MARTS_DATASET=mastr_marts
```

`GOOGLE_APPLICATION_CREDENTIALS` here should point at that **ADC file**, not a service-account JSON private key. The dashboard builds `bigquery.Client` via ADC (`google.auth` default credentials).

A separate MaStR ADC **path** only isolates which credentials file is loaded. It does **not** create a different Google user identity and does **not** grant a separate refresh-token. The file still represents the same user credential (and impersonation target) that produced it.

Do **not** run `gcloud auth application-default login` solely for this dashboard if that would replace an existing default ADC you still need. If you already have a suitable already-impersonated ADC, copy it into the MaStR path above.

Do **not** create or mount service-account private keys for this local dashboard.

## Install

```bash
cd /path/to/mastr-project/mastr-dashboard
cp .env.sample .env   # set YOUR_USER path and project if needed
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

Tests do not call BigQuery or read credential contents.

## Data sources

| Source | Use |
|--------|-----|
| `mastr_marts.mart_municipality_capacity` | Overview KPIs and charts |
| `mastr_marts.dim_municipality` | Municipality attributes (via mart) |
| `mastr_marts.dim_energy_source` / `fct_mastr_units` | Available for source-level queries |
| Geobasis BB OGC API `gem` collection | Municipality polygons (`krss=12069`) |

Join key for the map: Gold `municipality_id` = GeoJSON property `ags`.

## Notes

- Implemented as a **local** Streamlit app; production hosting and deployment are not implemented.
- Requires live BigQuery access to Gold tables at runtime.
- CDC change fact (`fct_mastr_unit_changes`) is not charted yet (fact is empty until eligible snapshot pairs exist).
- Do not commit credentials or `.env` files.
