# MaStR Dashboard

Interactive Streamlit dashboard comparing renewable energy generation and battery storage capacity across **38 municipalities in Potsdam-Mittelmark, Germany**.

## Features

- Overview KPIs: generation MW, storage MWh, installations
- Capacity by energy source (solar, wind, biomass)
- Top 10 municipalities by generation
- Generation vs. storage comparisons
- Municipality and energy source filters
- Interactive municipality map using Geobasis Brandenburg boundaries

## Tech Stack

Streamlit, Python, Altair, PyDeck, BigQuery.

Data comes from the BigQuery Gold dataset (`mastr_marts`).

## Setup

**Requirements:** Docker Compose or Python 3.12 + Poetry, and GCP Application Default Credentials (ADC) with BigQuery access.

```bash
cp .env.sample .env
```

Configure `.env` with `GCP_PROJECT_ID`, `BQ_LOCATION`, `BQ_MARTS_DATASET`, and the absolute `GOOGLE_APPLICATION_CREDENTIALS` path to your existing ADC file.

## Run with Docker

```bash
make up
```

Open http://localhost:8501.

```bash
make logs
make down
```

## Run with Poetry

```bash
make install
make run
```

## Tests

```bash
make test
```

The dashboard reads municipality capacity data from BigQuery and uses Geobasis Brandenburg municipality boundaries for the interactive map.