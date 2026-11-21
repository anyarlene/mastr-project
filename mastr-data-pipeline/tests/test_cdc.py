"""Synthetic snapshot CDC classification tests (no BigQuery / dbt run)."""

from __future__ import annotations

from mastr_data_pipeline.cdc import (
    CHANGE_DELETE_CANDIDATE,
    CHANGE_INSERT,
    CHANGE_UNCHANGED,
    CHANGE_UPDATE,
    TRACKED_ATTRIBUTES,
    classify_unit_change,
    consecutive_snapshot_pairs,
    detect_snapshot_changes,
    eligible_snapshot_dates,
    tracked_attributes_differ,
    values_differ,
)


def _unit(
    *,
    status_code: str = "operational",
    net_power_kw: float | None = 10.0,
    storage_capacity_kwh: float | None = None,
    municipality_id: str | None = "12069000",
    source_file: str = "solar.csv",
) -> dict:
    return {
        "status_code": status_code,
        "net_power_kw": net_power_kw,
        "storage_capacity_kwh": storage_capacity_kwh,
        "municipality_id": municipality_id,
        "source_file": source_file,
    }


def test_null_safe_values_differ():
    assert values_differ(None, None) is False
    assert values_differ(None, 1) is True
    assert values_differ(1, None) is True
    assert values_differ(1.0, 1.0) is False
    assert values_differ("a", "b") is True


def test_classify_insert_update_delete_unchanged():
    before = _unit(net_power_kw=10.0)
    after_same = _unit(net_power_kw=10.0)
    after_power = _unit(net_power_kw=12.5)
    after_status = _unit(status_code="decommissioned")
    after_null_capacity = _unit(storage_capacity_kwh=None)
    before_null_capacity = _unit(storage_capacity_kwh=None)

    assert classify_unit_change(None, after_same) == CHANGE_INSERT
    assert classify_unit_change(before, None) == CHANGE_DELETE_CANDIDATE
    assert classify_unit_change(before, after_same) == CHANGE_UNCHANGED
    assert classify_unit_change(before, after_power) == CHANGE_UPDATE
    assert classify_unit_change(before, after_status) == CHANGE_UPDATE
    # Null-safe: both missing capacity is not an UPDATE by itself
    assert (
        classify_unit_change(before_null_capacity, after_null_capacity)
        == CHANGE_UNCHANGED
    )
    assert (
        classify_unit_change(
            _unit(storage_capacity_kwh=None),
            _unit(storage_capacity_kwh=5.0),
        )
        == CHANGE_UPDATE
    )


def test_tracked_attributes_cover_required_fields():
    assert TRACKED_ATTRIBUTES == (
        "status_code",
        "net_power_kw",
        "storage_capacity_kwh",
        "municipality_id",
    )
    assert tracked_attributes_differ(
        _unit(municipality_id="1"),
        _unit(municipality_id="2"),
    )


def test_eligible_dates_require_all_statuses_and_complete():
    metadata = {
        "2026-11-09": {"export_scope": "legacy_mixed_filters", "cdc_baseline": False},
        "2026-11-16": {"export_scope": "all_statuses", "cdc_baseline": True},
        "2026-11-23": {"export_scope": "all_statuses", "cdc_baseline": True},
    }
    complete = ["2026-11-09", "2026-11-16", "2026-11-23"]
    assert eligible_snapshot_dates(metadata, complete) == [
        "2026-11-16",
        "2026-11-23",
    ]
    # Incomplete all_statuses date is excluded
    assert eligible_snapshot_dates(metadata, ["2026-11-09", "2026-11-16"]) == [
        "2026-11-16"
    ]


def test_single_eligible_snapshot_yields_no_pairs_or_events():
    metadata = {
        "2026-11-09": {"export_scope": "legacy_mixed_filters", "cdc_baseline": False},
        "2026-11-16": {"export_scope": "all_statuses", "cdc_baseline": True},
    }
    eligible = eligible_snapshot_dates(
        metadata, ["2026-11-09", "2026-11-16"]
    )
    assert eligible == ["2026-11-16"]
    assert consecutive_snapshot_pairs(eligible) == []

    # With only one synthetic "current" map and no previous, detector still
    # needs two maps; empty pairs means callers emit no CDC events.
    assert detect_snapshot_changes({}, {}) == []


def test_detect_synthetic_snapshot_change_types_idempotent():
    from_units = {
        "SEE_KEEP": _unit(net_power_kw=10.0),
        "SEE_UPDATE": _unit(status_code="operational", net_power_kw=10.0),
        "SEE_DELETE": _unit(source_file="wind.csv"),
    }
    to_units = {
        "SEE_KEEP": _unit(net_power_kw=10.0),
        "SEE_UPDATE": _unit(status_code="planned", net_power_kw=10.0),
        "SEE_INSERT": _unit(source_file="biomass.csv", net_power_kw=100.0),
    }

    first = detect_snapshot_changes(from_units, to_units)
    second = detect_snapshot_changes(from_units, to_units)
    assert first == second

    by_id = {e["unit_id"]: e["change_type"] for e in first}
    assert by_id == {
        "SEE_UPDATE": CHANGE_UPDATE,
        "SEE_DELETE": CHANGE_DELETE_CANDIDATE,
        "SEE_INSERT": CHANGE_INSERT,
    }
    assert "SEE_KEEP" not in by_id

    with_unchanged = detect_snapshot_changes(
        from_units, to_units, include_unchanged=True
    )
    assert {e["unit_id"]: e["change_type"] for e in with_unchanged}["SEE_KEEP"] == (
        CHANGE_UNCHANGED
    )


def test_nov9_excluded_from_cdc_pairs_when_present_with_nov16():
    metadata = {
        "2026-11-09": {"export_scope": "legacy_mixed_filters", "cdc_baseline": False},
        "2026-11-16": {"export_scope": "all_statuses", "cdc_baseline": True},
    }
    pairs = consecutive_snapshot_pairs(
        eligible_snapshot_dates(metadata, ["2026-11-09", "2026-11-16"])
    )
    assert pairs == []
