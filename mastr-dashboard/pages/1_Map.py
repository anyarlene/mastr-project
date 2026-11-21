"""Interactive municipality choropleth for Potsdam-Mittelmark."""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from utils.bigquery import (
    apply_energy_source,
    generation_vs_storage,
    load_municipality_capacity,
)
from utils.filters import render_sidebar_filters
from utils.geo import (
    POTSDAM_MITTELMARK_KRSS,
    UNSELECTED_FILL,
    apply_feature_colors,
    fetch_municipality_geojson,
    geojson_bounds,
    join_capacity_to_geojson,
    legend_stops,
    match_municipalities,
    view_state_from_bounds,
)

st.set_page_config(page_title="MaStR Municipality Map", layout="wide")

st.title("Renewable Energy Capacity — Potsdam-Mittelmark")
st.caption("Installed renewable generation and storage capacity across 38 municipalities.")


@st.cache_data(ttl=600, show_spinner="Loading capacity…")
def get_capacity() -> pd.DataFrame:
    return load_municipality_capacity()


@st.cache_data(ttl=3600, show_spinner="Loading municipality boundaries…")
def get_geojson() -> dict:
    return fetch_municipality_geojson()


def _rgba_css(color: list[int]) -> str:
    return f"rgba({color[0]}, {color[1]}, {color[2]}, {(color[3] / 255):.2f})"


try:
    capacity = get_capacity()
    geojson = get_geojson()
except Exception as exc:  # pragma: no cover - UI path
    st.error(f"Could not load map inputs: {exc}")
    st.stop()

if not capacity.empty and set(capacity["district"].astype(str)) != {"Potsdam-Mittelmark"}:
    st.error("Unexpected districts in Gold data; expected Potsdam-Mittelmark only.")
    st.stop()

match = match_municipalities(capacity, geojson)
if not match["is_complete"]:
    st.warning(
        "Experimental map: geographic join is incomplete. "
        f"Matched {match['matched_count']} of {match['gold_count']} Gold municipalities. "
        f"Missing in GeoJSON: {match['missing_in_geo'] or 'none'}. "
        f"Extra in GeoJSON: {match['missing_in_gold'] or 'none'}."
    )
else:
    st.success(
        f"Geographic join complete: {match['matched_count']} / "
        f"{match['gold_count']} municipalities matched on AGS "
        f"(district krss={POTSDAM_MITTELMARK_KRSS})."
    )

selected_municipalities, source_code = render_sidebar_filters(capacity)

metric = st.radio(
    "Color by",
    options=["Generation (MW)", "Storage (MWh)"],
    horizontal=True,
)
value_column = "generation_mw" if metric.startswith("Generation") else "storage_mwh"
unit_label = "MW" if value_column == "generation_mw" else "MWh"

# Energy source updates generation values for all 38 municipalities.
# Municipality selection only changes which polygons are highlighted.
with_source = apply_energy_source(capacity, energy_source=source_code)
enriched_capacity = generation_vs_storage(with_source)
selected_ids = set(
    enriched_capacity.loc[
        enriched_capacity["municipality_name"].isin(selected_municipalities),
        "municipality_id",
    ].astype(str)
)

joined = join_capacity_to_geojson(
    enriched_capacity,
    geojson,
    value_column=value_column,
    selected_ids=selected_ids,
)

# Scale colors from selected municipalities only so filters stay readable.
selected_values = [
    feature["properties"].get("value")
    for feature in joined.get("features", [])
    if feature["properties"].get("selected") and feature["properties"].get("matched")
]
vmax = max([v for v in selected_values if v is not None] or [0.0])
joined = apply_feature_colors(joined, vmax=vmax)

bounds = geojson_bounds(joined)
view = view_state_from_bounds(bounds)
view_state = pdk.ViewState(**view)

tooltip = {
    "html": (
        "<b>{municipality_name}</b><br/>"
        "Generation: {generation_mw} MW<br/>"
        "Storage: {storage_mwh} MWh"
    ),
    "style": {"backgroundColor": "#1b1b1b", "color": "white"},
}

layer = pdk.Layer(
    "GeoJsonLayer",
    joined,
    opacity=0.9,
    stroked=True,
    filled=True,
    get_fill_color="properties.fill_color",
    get_line_color="properties.line_color",
    line_width_min_pixels=1,
    pickable=True,
    auto_highlight=True,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="light",
    ),
    use_container_width=True,
)

# Color legend (generation MW or storage MWh — never mixed).
st.markdown(f"**Legend — {metric}**")
stops = legend_stops(vmax)
legend_cols = st.columns(len(stops) + 1)
for column, (label, color) in zip(legend_cols, stops):
    column.markdown(
        f"<div style='height:14px;background:{_rgba_css(color)};"
        f"border:1px solid #777;border-radius:2px;'></div>"
        f"<small>{label} {unit_label}</small>",
        unsafe_allow_html=True,
    )
legend_cols[-1].markdown(
    f"<div style='height:14px;background:{_rgba_css(UNSELECTED_FILL)};"
    f"border:1px solid #777;border-radius:2px;'></div>"
    f"<small>Unselected</small>",
    unsafe_allow_html=True,
)

st.caption(
    "Boundaries: Geobasis Brandenburg OGC API "
    f"`gem` collection filtered to krss={POTSDAM_MITTELMARK_KRSS} only. "
    "All 38 district municipalities stay visible; unselected areas are greyed out. "
    "Capacity from BigQuery Gold mart."
)

with st.expander("Match details"):
    st.json(
        {
            "matched_count": match["matched_count"],
            "gold_count": match["gold_count"],
            "geo_count": match["geo_count"],
            "feature_count": len(joined.get("features", [])),
            "selected_count": len(selected_ids),
            "is_complete": match["is_complete"],
            "missing_in_geo": match["missing_in_geo"],
            "missing_in_gold": match["missing_in_gold"],
            "bounds": bounds,
        }
    )
