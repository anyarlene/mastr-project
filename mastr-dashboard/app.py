"""MaStR capacity overview dashboard (Streamlit PoC)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from utils.bigquery import (
    apply_energy_source,
    capacity_by_source_from_mart,
    filter_municipalities,
    generation_vs_storage,
    load_municipality_capacity,
    summarize_kpis,
    top_municipalities,
)
from utils.filters import render_sidebar_filters

st.set_page_config(
    page_title="MaStR Capacity Overview",
    page_icon=None,
    layout="wide",
)

st.title("Renewable Energy Capacity — Potsdam-Mittelmark")
st.caption("Installed renewable generation and storage capacity across 38 municipalities.")


@st.cache_data(ttl=600, show_spinner="Loading Gold capacity…")
def get_capacity() -> pd.DataFrame:
    return load_municipality_capacity()


try:
    capacity = get_capacity()
except Exception as exc:  # pragma: no cover - UI path
    st.error(f"Could not load BigQuery data: {exc}")
    st.stop()

# Guard: Gold mart must stay within the district.
if not capacity.empty and set(capacity["district"].astype(str)) != {"Potsdam-Mittelmark"}:
    st.error("Unexpected districts in Gold data; expected Potsdam-Mittelmark only.")
    st.stop()

selected_municipalities, source_code = render_sidebar_filters(capacity)

# Energy source applies to all rows; municipality filter scopes KPIs/charts.
with_source = apply_energy_source(capacity, energy_source=source_code)
filtered = filter_municipalities(with_source, municipalities=selected_municipalities)
kpis = summarize_kpis(filtered)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Operational generation", f"{kpis['generation_mw']:,.1f} MW")
col2.metric("Operational storage", f"{kpis['storage_mwh']:,.1f} MWh")
col3.metric("Operational installations", f"{kpis['installations']:,}")
col4.metric("Municipalities", f"{kpis['municipalities']}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Installed generation by energy source")
    by_source = capacity_by_source_from_mart(filtered)
    if source_code:
        by_source = by_source[by_source["energy_source_code"] == source_code]
    chart_source = (
        alt.Chart(by_source)
        .mark_bar()
        .encode(
            x=alt.X("generation_mw:Q", title="Installed capacity (MW)"),
            y=alt.Y("energy_source_label:N", sort="-x", title="Energy source"),
            tooltip=[
                alt.Tooltip("energy_source_label:N", title="Source"),
                alt.Tooltip("generation_mw:Q", title="MW", format=",.2f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart_source, use_container_width=True)

with right:
    st.subheader("Top 10 municipalities by generation")
    top = top_municipalities(filtered, n=10)
    chart_top = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("generation_mw:Q", title="Generation capacity (MW)"),
            y=alt.Y("municipality_name:N", sort="-x", title="Municipality"),
            tooltip=[
                alt.Tooltip("municipality_name:N", title="Municipality"),
                alt.Tooltip("generation_mw:Q", title="Generation MW", format=",.2f"),
                alt.Tooltip("storage_mwh:Q", title="Storage MWh", format=",.2f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart_top, use_container_width=True)

st.subheader("Generation vs storage by municipality")
st.caption(
    "Generation is shown in MW (net rated power). "
    "Storage is shown in MWh (usable capacity). Measures are not mixed."
)
compare = generation_vs_storage(filtered)
compare_long = compare.melt(
    id_vars=["municipality_id", "municipality_name"],
    value_vars=["generation_mw", "storage_mwh"],
    var_name="measure",
    value_name="value",
)
compare_long["measure_label"] = compare_long["measure"].map(
    {
        "generation_mw": "Generation (MW)",
        "storage_mwh": "Storage (MWh)",
    }
)

chart_compare = (
    alt.Chart(compare_long)
    .mark_bar()
    .encode(
        x=alt.X("municipality_name:N", sort="-y", title="Municipality"),
        y=alt.Y("value:Q", title="Capacity"),
        color=alt.Color(
            "measure_label:N",
            title="Measure",
            scale=alt.Scale(
                domain=["Generation (MW)", "Storage (MWh)"],
                range=["#2f6f4e", "#c47b2d"],
            ),
        ),
        xOffset="measure_label:N",
        tooltip=[
            alt.Tooltip("municipality_name:N", title="Municipality"),
            alt.Tooltip("measure_label:N", title="Measure"),
            alt.Tooltip("value:Q", title="Value", format=",.2f"),
        ],
    )
    .properties(height=360)
)
st.altair_chart(chart_compare, use_container_width=True)

with st.expander("Data preview"):
    preview = filtered[
        [
            "municipality_name",
            "selected_generation_power_kw",
            "operational_storage_capacity_kwh",
            "operational_generation_unit_count",
            "operational_storage_unit_count",
        ]
    ].copy()
    preview["generation_mw"] = preview["selected_generation_power_kw"].astype(float) / 1000
    preview["storage_mwh"] = preview["operational_storage_capacity_kwh"].astype(float) / 1000
    st.dataframe(
        preview[
            [
                "municipality_name",
                "generation_mw",
                "storage_mwh",
                "operational_generation_unit_count",
                "operational_storage_unit_count",
            ]
        ].sort_values("generation_mw", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
