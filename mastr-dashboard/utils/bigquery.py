"""Read-only BigQuery helpers for MaStR Gold marts."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

PROJECT_ID = "your-gcp-project-id"
DATASET = "mastr_marts"
LOCATION = "europe-west3"

KW_TO_MW = 1000.0
KWH_TO_MWH = 1000.0

# Display labels for generation sources available in the mart.
GENERATION_SOURCES = {
    "wind": "Wind",
    "solar": "Solar",
    "biomass": "Biomass",
}


def _default_credentials_path() -> str:
    return os.path.expanduser("~/.gcp_keys/dbt-service-account.json")


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    """Build a BigQuery client from local service-account credentials."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    keyfile = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", _default_credentials_path())
    project = os.environ.get("GCP_PROJECT_ID", PROJECT_ID)
    return bigquery.Client.from_service_account_json(keyfile, project=project, location=LOCATION)


def run_query(sql: str) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame."""
    return get_client().query(sql, location=LOCATION).to_dataframe(create_bqstorage_client=False)


def load_municipality_capacity() -> pd.DataFrame:
    """Latest operational capacity per municipality from the Gold mart."""
    sql = f"""
    select
        municipality_id,
        municipality_name,
        district,
        federal_state,
        snapshot_date,
        operational_generation_power_kw,
        operational_wind_power_kw,
        operational_solar_power_kw,
        operational_biomass_power_kw,
        operational_storage_power_kw,
        operational_storage_capacity_kwh,
        operational_generation_unit_count,
        operational_storage_unit_count
    from `{PROJECT_ID}.{DATASET}.mart_municipality_capacity`
    order by municipality_name
    """
    return run_query(sql)


def load_capacity_by_energy_source() -> pd.DataFrame:
    """Operational generation capacity (kW) by energy source for the mart snapshot."""
    sql = f"""
    select
        e.energy_source_code,
        e.energy_source_label,
        e.energy_source_group,
        sum(f.generation_power_kw) as generation_power_kw,
        sum(f.storage_capacity_kwh) as storage_capacity_kwh,
        count(*) as unit_count
    from `{PROJECT_ID}.{DATASET}.fct_mastr_units` as f
    inner join `{PROJECT_ID}.{DATASET}.dim_energy_source` as e
        on f.energy_source_id = e.energy_source_id
    inner join `{PROJECT_ID}.{DATASET}.mart_municipality_capacity` as m
        on f.snapshot_date = m.snapshot_date
        and f.municipality_id = m.municipality_id
    where f.is_operational = true
      and e.energy_source_group = 'generation'
    group by e.energy_source_code, e.energy_source_label, e.energy_source_group
    order by generation_power_kw desc
    """
    return run_query(sql)


def kw_to_mw(series: pd.Series) -> pd.Series:
    return series.astype(float) / KW_TO_MW


def kwh_to_mwh(series: pd.Series) -> pd.Series:
    return series.astype(float) / KWH_TO_MWH


def apply_energy_source(
    df: pd.DataFrame,
    energy_source: str | None = None,
) -> pd.DataFrame:
    """
    Set selected_generation_power_kw from total generation or one source.

    Keeps all municipality rows. Storage columns are unchanged.
    """
    out = df.copy()
    if energy_source and energy_source in GENERATION_SOURCES:
        out["selected_generation_power_kw"] = out[f"operational_{energy_source}_power_kw"]
    else:
        out["selected_generation_power_kw"] = out["operational_generation_power_kw"]
    return out


def filter_municipalities(
    df: pd.DataFrame,
    municipalities: list[str] | None = None,
) -> pd.DataFrame:
    """Keep only selected municipality names. None keeps all rows."""
    out = df.copy()
    if municipalities is None:
        return out
    return out[out["municipality_name"].isin(municipalities)].copy()


def filter_capacity(
    df: pd.DataFrame,
    municipalities: list[str] | None = None,
    energy_source: str | None = None,
) -> pd.DataFrame:
    """Apply energy-source selection, then optionally filter municipalities."""
    out = apply_energy_source(df, energy_source=energy_source)
    return filter_municipalities(out, municipalities=municipalities)


def summarize_kpis(df: pd.DataFrame) -> dict[str, float | int]:
    """Aggregate overview KPIs from a filtered municipality capacity frame."""
    if df.empty:
        return {
            "generation_mw": 0.0,
            "storage_mwh": 0.0,
            "installations": 0,
            "municipalities": 0,
        }
    gen_kw = df["selected_generation_power_kw"].astype(float).sum()
    storage_kwh = df["operational_storage_capacity_kwh"].astype(float).sum()
    installations = int(
        df["operational_generation_unit_count"].fillna(0).sum()
        + df["operational_storage_unit_count"].fillna(0).sum()
    )
    return {
        "generation_mw": gen_kw / KW_TO_MW,
        "storage_mwh": storage_kwh / KWH_TO_MWH,
        "installations": installations,
        "municipalities": int(df["municipality_id"].nunique()),
    }


def capacity_by_source_from_mart(df: pd.DataFrame) -> pd.DataFrame:
    """Build a long table of generation capacity by source from mart columns."""
    rows = []
    for code, label in GENERATION_SOURCES.items():
        col = f"operational_{code}_power_kw"
        rows.append(
            {
                "energy_source_code": code,
                "energy_source_label": label,
                "generation_mw": float(df[col].astype(float).sum()) / KW_TO_MW,
            }
        )
    return pd.DataFrame(rows)


def top_municipalities(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top N municipalities by selected generation capacity (MW)."""
    out = df[
        [
            "municipality_id",
            "municipality_name",
            "selected_generation_power_kw",
            "operational_storage_capacity_kwh",
        ]
    ].copy()
    out["generation_mw"] = out["selected_generation_power_kw"].astype(float) / KW_TO_MW
    out["storage_mwh"] = out["operational_storage_capacity_kwh"].astype(float) / KWH_TO_MWH
    return out.nlargest(n, "generation_mw")


def generation_vs_storage(df: pd.DataFrame) -> pd.DataFrame:
    """Municipality-level generation MW and storage MWh for comparison charts."""
    out = df[
        [
            "municipality_id",
            "municipality_name",
            "selected_generation_power_kw",
            "operational_storage_capacity_kwh",
        ]
    ].copy()
    out["generation_mw"] = out["selected_generation_power_kw"].astype(float) / KW_TO_MW
    out["storage_mwh"] = out["operational_storage_capacity_kwh"].astype(float) / KWH_TO_MWH
    return out.sort_values("generation_mw", ascending=False)
