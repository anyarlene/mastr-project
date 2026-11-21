"""Shared Streamlit sidebar filters for overview and map pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.bigquery import GENERATION_SOURCES

SOURCE_OPTIONS = ["All generation sources", "Solar", "Wind", "Biomass"]
SOURCE_LABEL_TO_CODE = {label: code for code, label in GENERATION_SOURCES.items()}


def municipality_options(capacity: pd.DataFrame) -> list[str]:
    """Sorted municipality names from the Gold mart (Potsdam-Mittelmark)."""
    return sorted(capacity["municipality_name"].astype(str).unique().tolist())


def render_sidebar_filters(capacity: pd.DataFrame) -> tuple[list[str], str | None]:
    """
    Render municipality and energy-source filters.

    Returns selected municipality names and an optional generation source code
    (None means all generation sources). Filters are independent.
    """
    options = municipality_options(capacity)
    snapshot = capacity["snapshot_date"].iloc[0] if not capacity.empty else "n/a"

    st.sidebar.header("Filters")
    st.sidebar.write(f"Snapshot date: **{snapshot}**")
    st.sidebar.caption(f"{len(options)} municipalities in Potsdam-Mittelmark")

    select_all = st.sidebar.checkbox(
        "Select all municipalities",
        value=True,
        key="filter_select_all",
        help="When checked, all 38 municipalities are included.",
    )
    if select_all:
        selected_municipalities = options
        st.sidebar.write(f"All **{len(options)}** municipalities selected")
    else:
        selected_municipalities = st.sidebar.multiselect(
            "Municipality",
            options=options,
            default=options,
            key="filter_municipalities",
            help="Select one or more municipalities within Potsdam-Mittelmark.",
        )

    source_label = st.sidebar.selectbox(
        "Energy source",
        options=SOURCE_OPTIONS,
        index=0,
        key="filter_energy_source",
        help="Filters generation capacity only. Storage stays a separate measure.",
    )
    source_code = SOURCE_LABEL_TO_CODE.get(source_label)

    st.session_state["selected_municipalities"] = selected_municipalities
    st.session_state["energy_source_code"] = source_code
    return selected_municipalities, source_code
