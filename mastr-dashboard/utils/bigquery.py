"""Read-only BigQuery helpers for MaStR Gold marts."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

# Product Gold dataset contract (overridable via BQ_MARTS_DATASET).
DEFAULT_MARTS_DATASET = "mastr_marts"

KW_TO_MW = 1000.0
KWH_TO_MWH = 1000.0

# Display labels for generation sources available in the mart.
GENERATION_SOURCES = {
    "wind": "Wind",
    "solar": "Solar",
    "biomass": "Biomass",
}

_ENV_LOADED = False


def _load_env() -> None:
    """Load dashboard .env once (if present). Does not override existing env vars."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    _ENV_LOADED = True


def _require_env(name: str) -> str:
    _load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            f"Set it in .env (see .env.sample) or the process environment."
        )
    return value


def get_project_id() -> str:
    """Return the BigQuery project id from GCP_PROJECT_ID."""
    return _require_env("GCP_PROJECT_ID")


def get_location() -> str:
    """Return the BigQuery location from BQ_LOCATION."""
    return _require_env("BQ_LOCATION")


def get_marts_dataset() -> str:
    """Return the Gold/marts dataset (BQ_MARTS_DATASET or product default)."""
    _load_env()
    value = os.environ.get("BQ_MARTS_DATASET", DEFAULT_MARTS_DATASET).strip()
    return value or DEFAULT_MARTS_DATASET


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    """Build a BigQuery client via Application Default Credentials (ADC)."""
    return bigquery.Client(project=get_project_id(), location=get_location())


def run_query(sql: str) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame."""
    location = get_location()
    return get_client().query(sql, location=location).to_dataframe(
        create_bqstorage_client=False
    )


def load_municipality_capacity() -> pd.DataFrame:
    """Latest operational capacity per municipality from the Gold mart."""
    project = get_project_id()
    dataset = get_marts_dataset()
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
    from `{project}.{dataset}.mart_municipality_capacity`
    order by municipality_name
    """
    return run_query(sql)


def load_capacity_by_energy_source() -> pd.DataFrame:
    """Operational generation capacity (kW) by energy source for the mart snapshot."""
    project = get_project_id()
    dataset = get_marts_dataset()
    sql = f"""
    select
        e.energy_source_code,
        e.energy_source_label,
        e.energy_source_group,
        sum(f.generation_power_kw) as generation_power_kw,
        sum(f.storage_capacity_kwh) as storage_capacity_kwh,
        count(*) as unit_count
    from `{project}.{dataset}.fct_mastr_units` as f
    inner join `{project}.{dataset}.dim_energy_source` as e
        on f.energy_source_id = e.energy_source_id
    inner join `{project}.{dataset}.mart_municipality_capacity` as m
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
