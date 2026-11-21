"""Tests for AGS / municipality_id geographic matching and map helpers."""

from __future__ import annotations

import pandas as pd

from utils.geo import (
    POTSDAM_MITTELMARK_KRSS,
    UNSELECTED_FILL,
    apply_feature_colors,
    extract_ags_index,
    geojson_bounds,
    join_capacity_to_geojson,
    legend_stops,
    match_municipalities,
    view_state_from_bounds,
)


def _sample_geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ags": "12069017", "gem_name": "Beelitz", "krss": "12069"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[12.0, 52.0], [12.2, 52.0], [12.2, 52.2], [12.0, 52.0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"ags": "12069632", "gem_name": "Treuenbrietzen", "krss": "12069"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[12.3, 52.1], [12.5, 52.1], [12.5, 52.3], [12.3, 52.1]]],
                },
            },
        ],
    }


def _sample_capacity() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "municipality_id": "12069017",
                "municipality_name": "Beelitz",
                "generation_mw": 10.5,
                "storage_mwh": 2.0,
            },
            {
                "municipality_id": "12069632",
                "municipality_name": "Treuenbrietzen",
                "generation_mw": 20.0,
                "storage_mwh": 3.5,
            },
        ]
    )


def test_extract_ags_index() -> None:
    index = extract_ags_index(_sample_geojson())
    assert index["12069017"] == "Beelitz"
    assert len(index) == 2


def test_match_municipalities_complete() -> None:
    result = match_municipalities(_sample_capacity(), _sample_geojson())
    assert result["is_complete"] is True
    assert result["matched_count"] == 2
    assert result["missing_in_geo"] == []
    assert result["missing_in_gold"] == []


def test_match_municipalities_incomplete() -> None:
    capacity = _sample_capacity()
    capacity = pd.concat(
        [
            capacity,
            pd.DataFrame(
                [
                    {
                        "municipality_id": "99999999",
                        "municipality_name": "Unknown",
                        "generation_mw": 1.0,
                        "storage_mwh": 0.1,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    result = match_municipalities(capacity, _sample_geojson())
    assert result["is_complete"] is False
    assert result["missing_in_geo"] == ["99999999"]


def test_join_capacity_to_geojson_attaches_metrics() -> None:
    joined = join_capacity_to_geojson(_sample_capacity(), _sample_geojson(), value_column="generation_mw")
    props = {f["properties"]["ags"]: f["properties"] for f in joined["features"]}
    assert props["12069017"]["matched"] is True
    assert props["12069017"]["generation_mw"] == 10.5
    assert props["12069017"]["value"] == 10.5
    assert props["12069017"]["selected"] is True


def test_join_keeps_all_boundaries_with_partial_selection() -> None:
    joined = join_capacity_to_geojson(
        _sample_capacity(),
        _sample_geojson(),
        value_column="generation_mw",
        selected_ids={"12069017"},
    )
    assert len(joined["features"]) == 2
    props = {f["properties"]["ags"]: f["properties"] for f in joined["features"]}
    assert props["12069017"]["selected"] is True
    assert props["12069632"]["selected"] is False

    colored = apply_feature_colors(joined, vmax=10.5)
    colored_props = {f["properties"]["ags"]: f["properties"] for f in colored["features"]}
    assert colored_props["12069632"]["fill_color"] == list(UNSELECTED_FILL)
    assert colored_props["12069017"]["fill_color"] != list(UNSELECTED_FILL)


def test_bounds_and_legend() -> None:
    bounds = geojson_bounds(_sample_geojson())
    assert bounds == (12.0, 52.0, 12.5, 52.3)
    view = view_state_from_bounds(bounds)
    assert 12.0 < view["longitude"] < 12.5
    assert 52.0 < view["latitude"] < 52.3
    assert view["zoom"] >= 6.0

    stops = legend_stops(20.0, steps=3)
    assert len(stops) == 3
    assert stops[0][0] == "0.0"
    assert stops[-1][0] == "20.0"
    assert POTSDAM_MITTELMARK_KRSS == "12069"
