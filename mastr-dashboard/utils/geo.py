"""Fetch and match Brandenburg municipality boundaries for Potsdam-Mittelmark."""

from __future__ import annotations

import copy
import math
from typing import Any

import pandas as pd
import requests

GEO_API_URL = (
    "https://ogc-api.geobasis-bb.de/datasets/vg/collections/gem/items"
)
# Official district code for Landkreis Potsdam-Mittelmark.
POTSDAM_MITTELMARK_KRSS = "12069"

# Unselected municipalities stay visible but muted.
UNSELECTED_FILL = [210, 210, 210, 120]
UNSELECTED_LINE = [120, 120, 120]


def fetch_municipality_geojson(
    krss: str = POTSDAM_MITTELMARK_KRSS,
    timeout: int = 60,
) -> dict[str, Any]:
    """Download GeoJSON municipality polygons for one Brandenburg district."""
    response = requests.get(
        GEO_API_URL,
        params={"f": "json", "limit": 100, "krss": krss},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    # Keep only the requested district (exclude Potsdam city and others).
    features = [
        feature
        for feature in data.get("features", [])
        if str((feature.get("properties") or {}).get("krss", "")) == str(krss)
    ]
    data["features"] = features
    data["numberReturned"] = len(features)
    return data


def extract_ags_index(geojson: dict[str, Any]) -> dict[str, str]:
    """Map AGS codes to municipality names from GeoJSON properties."""
    index: dict[str, str] = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties") or {}
        ags = props.get("ags")
        name = props.get("gem_name")
        if ags and name:
            index[str(ags)] = str(name)
    return index


def match_municipalities(
    capacity: pd.DataFrame,
    geojson: dict[str, Any],
) -> dict[str, Any]:
    """
    Match Gold municipality_id values to GeoJSON AGS codes.

    Returns match counts and lists of unmatched IDs on either side.
    """
    gold_ids = set(capacity["municipality_id"].astype(str))
    geo_ids = set(extract_ags_index(geojson))
    matched = sorted(gold_ids & geo_ids)
    return {
        "matched_count": len(matched),
        "gold_count": len(gold_ids),
        "geo_count": len(geo_ids),
        "matched_ids": matched,
        "missing_in_geo": sorted(gold_ids - geo_ids),
        "missing_in_gold": sorted(geo_ids - gold_ids),
        "is_complete": gold_ids == geo_ids and len(gold_ids) > 0,
    }


def join_capacity_to_geojson(
    capacity: pd.DataFrame,
    geojson: dict[str, Any],
    value_column: str = "generation_mw",
    selected_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    Attach capacity metrics to GeoJSON features by AGS = municipality_id.

    All district boundaries stay present. selected_ids controls highlighting.
    """
    lookup = {
        str(row.municipality_id): row
        for row in capacity.itertuples(index=False)
    }
    if selected_ids is None:
        selected_ids = set(lookup.keys())
    else:
        selected_ids = {str(item) for item in selected_ids}

    enriched = copy.deepcopy(geojson)
    for feature in enriched.get("features", []):
        props = feature.setdefault("properties", {})
        ags = str(props.get("ags", ""))
        row = lookup.get(ags)
        is_selected = ags in selected_ids
        props["selected"] = is_selected
        if row is None:
            props["municipality_name"] = props.get("gem_name")
            props["generation_mw"] = None
            props["storage_mwh"] = None
            props["value"] = None
            props["matched"] = False
            continue
        props["municipality_id"] = ags
        props["municipality_name"] = getattr(row, "municipality_name", props.get("gem_name"))
        props["generation_mw"] = float(getattr(row, "generation_mw", 0.0) or 0.0)
        props["storage_mwh"] = float(getattr(row, "storage_mwh", 0.0) or 0.0)
        props["value"] = float(getattr(row, value_column, 0.0) or 0.0)
        props["matched"] = True
    return enriched


def color_scale(value: float, vmax: float) -> list[int]:
    """Single-hue green scale for selected municipalities (light = low)."""
    if vmax <= 0 or value is None:
        return [220, 235, 220, 180]
    ratio = max(0.0, min(1.0, float(value) / float(vmax)))
    r = int(220 - ratio * 180)
    g = int(240 - ratio * 80)
    b = int(220 - ratio * 180)
    return [r, g, b, 200]


def apply_feature_colors(
    geojson: dict[str, Any],
    vmax: float,
) -> dict[str, Any]:
    """Set fill_color / line_color on each feature from selection and value."""
    for feature in geojson.get("features", []):
        props = feature.setdefault("properties", {})
        if props.get("selected") and props.get("matched"):
            props["fill_color"] = color_scale(props.get("value") or 0.0, vmax)
            props["line_color"] = [40, 40, 40]
        else:
            props["fill_color"] = list(UNSELECTED_FILL)
            props["line_color"] = list(UNSELECTED_LINE)
    return geojson


def _iter_coordinates(node: Any):
    """Yield [lon, lat] pairs from nested GeoJSON coordinate arrays."""
    if not isinstance(node, (list, tuple)) or not node:
        return
    if isinstance(node[0], (int, float)) and len(node) >= 2:
        yield float(node[0]), float(node[1])
        return
    for child in node:
        yield from _iter_coordinates(child)


def geojson_bounds(geojson: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) for all features."""
    lons: list[float] = []
    lats: list[float] = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        for lon, lat in _iter_coordinates(geometry.get("coordinates")):
            lons.append(lon)
            lats.append(lat)
    if not lons or not lats:
        # Fallback center of Potsdam-Mittelmark
        return (12.2, 52.0, 13.3, 52.7)
    return (min(lons), min(lats), max(lons), max(lats))


def view_state_from_bounds(
    bounds: tuple[float, float, float, float],
    width_px: int = 1000,
    height_px: int = 640,
) -> dict[str, float]:
    """Estimate a pydeck ViewState that fits the district bounds."""
    min_lon, min_lat, max_lon, max_lat = bounds
    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0

    # Pad slightly so borders are not clipped.
    pad = 0.04
    span_lat = max((max_lat - min_lat) * (1.0 + pad), 0.05)
    span_lon = max((max_lon - min_lon) * (1.0 + pad), 0.05)

    zoom_lat = math.log2(180.0 * (height_px / 256.0) / span_lat)
    zoom_lon = math.log2(360.0 * (width_px / 256.0) / span_lon)
    zoom = max(6.0, min(zoom_lat, zoom_lon) - 0.35)

    return {
        "latitude": center_lat,
        "longitude": center_lon,
        "zoom": zoom,
        "bearing": 0.0,
        "pitch": 0.0,
    }


def legend_stops(vmax: float, steps: int = 5) -> list[tuple[str, list[int]]]:
    """Build legend labels and colors from 0 to vmax."""
    if vmax <= 0:
        return [("0", color_scale(0.0, 1.0))]
    stops = []
    for index in range(steps):
        ratio = index / (steps - 1)
        value = vmax * ratio
        label = f"{value:,.1f}"
        stops.append((label, color_scale(value, vmax)))
    return stops
