"""Unit tests for dashboard transforms (no live BigQuery required)."""

from __future__ import annotations

import pandas as pd

from utils.bigquery import (
    apply_energy_source,
    capacity_by_source_from_mart,
    filter_capacity,
    filter_municipalities,
    summarize_kpis,
    top_municipalities,
)
from utils.filters import SOURCE_OPTIONS, municipality_options


def _sample_capacity() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "municipality_id": "12069017",
                "municipality_name": "Beelitz",
                "district": "Potsdam-Mittelmark",
                "operational_generation_power_kw": 10000.0,
                "operational_wind_power_kw": 6000.0,
                "operational_solar_power_kw": 3000.0,
                "operational_biomass_power_kw": 1000.0,
                "operational_storage_power_kw": 500.0,
                "operational_storage_capacity_kwh": 2000.0,
                "operational_generation_unit_count": 10,
                "operational_storage_unit_count": 4,
            },
            {
                "municipality_id": "12069020",
                "municipality_name": "Bad Belzig",
                "district": "Potsdam-Mittelmark",
                "operational_generation_power_kw": 8000.0,
                "operational_wind_power_kw": 1000.0,
                "operational_solar_power_kw": 6500.0,
                "operational_biomass_power_kw": 500.0,
                "operational_storage_power_kw": 400.0,
                "operational_storage_capacity_kwh": 1500.0,
                "operational_generation_unit_count": 8,
                "operational_storage_unit_count": 3,
            },
            {
                "municipality_id": "12069632",
                "municipality_name": "Treuenbrietzen",
                "district": "Potsdam-Mittelmark",
                "operational_generation_power_kw": 20000.0,
                "operational_wind_power_kw": 15000.0,
                "operational_solar_power_kw": 4000.0,
                "operational_biomass_power_kw": 1000.0,
                "operational_storage_power_kw": 800.0,
                "operational_storage_capacity_kwh": 3000.0,
                "operational_generation_unit_count": 20,
                "operational_storage_unit_count": 6,
            },
        ]
    )


def test_summarize_kpis_converts_units_and_counts() -> None:
    df = filter_capacity(_sample_capacity())
    kpis = summarize_kpis(df)
    assert round(kpis["generation_mw"], 3) == 38.0
    assert round(kpis["storage_mwh"], 3) == 6.5
    assert kpis["installations"] == 51
    assert kpis["municipalities"] == 3


def test_filter_by_municipality_and_energy_source() -> None:
    df = filter_capacity(
        _sample_capacity(),
        municipalities=["Beelitz"],
        energy_source="wind",
    )
    assert len(df) == 1
    assert float(df.iloc[0]["selected_generation_power_kw"]) == 6000.0
    kpis = summarize_kpis(df)
    assert round(kpis["generation_mw"], 3) == 6.0


def test_energy_source_independent_of_municipality_filter() -> None:
    all_rows = apply_energy_source(_sample_capacity(), energy_source="solar")
    assert len(all_rows) == 3
    assert round(float(all_rows["selected_generation_power_kw"].sum()) / 1000, 3) == 13.5

    belzig_solar = filter_municipalities(all_rows, municipalities=["Bad Belzig"])
    kpis = summarize_kpis(belzig_solar)
    assert round(kpis["generation_mw"], 3) == 6.5
    # Storage remains separate and is not treated as generation.
    assert round(kpis["storage_mwh"], 3) == 1.5


def test_wind_and_biomass_filters() -> None:
    wind = summarize_kpis(filter_capacity(_sample_capacity(), energy_source="wind"))
    biomass = summarize_kpis(filter_capacity(_sample_capacity(), energy_source="biomass"))
    assert round(wind["generation_mw"], 3) == 22.0
    assert round(biomass["generation_mw"], 3) == 2.5


def test_capacity_by_source_and_top_municipalities() -> None:
    df = filter_capacity(_sample_capacity())
    by_source = capacity_by_source_from_mart(df)
    assert set(by_source["energy_source_code"]) == {"wind", "solar", "biomass"}
    assert round(float(by_source.loc[by_source["energy_source_code"] == "wind", "generation_mw"].iloc[0]), 3) == 22.0

    top = top_municipalities(df, n=1)
    assert list(top["municipality_name"]) == ["Treuenbrietzen"]
    assert round(float(top.iloc[0]["generation_mw"]), 3) == 20.0


def test_municipality_options_and_source_labels() -> None:
    options = municipality_options(_sample_capacity())
    assert options == ["Bad Belzig", "Beelitz", "Treuenbrietzen"]
    assert SOURCE_OPTIONS[0] == "All generation sources"
    assert set(SOURCE_OPTIONS[1:]) == {"Solar", "Wind", "Biomass"}
