"""Unit tests for JSON configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastr_data_pipeline.config_loader import (
    SOURCE_FILES,
    load_german_headers,
    load_snapshots,
)
from mastr_data_pipeline.checksums import EXPECTED_SHA256, expected_checksums
from mastr_data_pipeline.raw_schema import EXPECTED_ROW_COUNTS, GERMAN_HEADERS


def test_repo_headers_match_loaded_constant():
    assert len(GERMAN_HEADERS) == 64
    assert GERMAN_HEADERS == load_german_headers()
    assert GERMAN_HEADERS[0] == "MaStR-Nr. der Einheit"
    assert GERMAN_HEADERS[-1] == "Thermische Nutzleistung in kW"


def test_repo_snapshots_populate_public_maps():
    snapshots = load_snapshots()
    assert "2026-11-09" in snapshots
    assert "2026-11-16" in snapshots
    assert snapshots["2026-11-09"]["export_scope"] == "legacy_mixed_filters"
    assert snapshots["2026-11-09"]["cdc_baseline"] is False
    assert snapshots["2026-11-16"]["export_scope"] == "all_statuses"
    assert snapshots["2026-11-16"]["cdc_baseline"] is True
    assert EXPECTED_ROW_COUNTS["2026-11-09"] == snapshots["2026-11-09"]["row_counts"]
    assert EXPECTED_ROW_COUNTS["2026-11-16"] == snapshots["2026-11-16"]["row_counts"]
    assert EXPECTED_SHA256["2026-11-09"] == snapshots["2026-11-09"]["sha256"]
    assert EXPECTED_SHA256["2026-11-16"] == snapshots["2026-11-16"]["sha256"]
    assert set(EXPECTED_SHA256["2026-11-09"]) == set(SOURCE_FILES)
    assert expected_checksums("2026-11-09") == EXPECTED_SHA256["2026-11-09"]
    assert sum(EXPECTED_ROW_COUNTS["2026-11-16"].values()) == 33643


def test_load_german_headers_rejects_wrong_count(tmp_path: Path):
    path = tmp_path / "mastr_headers.json"
    path.write_text(
        json.dumps({"version": 1, "columns": ["only_one"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected 64 columns"):
        load_german_headers(path)


def test_load_german_headers_rejects_duplicates(tmp_path: Path):
    columns = [f"col_{i}" for i in range(63)] + ["col_0"]
    path = tmp_path / "mastr_headers.json"
    path.write_text(
        json.dumps({"version": 1, "columns": columns}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate column"):
        load_german_headers(path)


def test_load_german_headers_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_german_headers(tmp_path / "missing.json")


def _snapshot_entry(**overrides):
    entry = {
        "export_scope": "legacy_mixed_filters",
        "cdc_baseline": False,
        "row_counts": {name: 1 for name in SOURCE_FILES},
        "sha256": {name: "a" * 64 for name in SOURCE_FILES},
    }
    entry.update(overrides)
    return entry


def test_load_snapshots_rejects_incomplete_sha_keys(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    entry = _snapshot_entry(
        sha256={name: "a" * 64 for name in SOURCE_FILES if name != "wind.csv"}
    )
    payload = {"version": 1, "snapshots": {"2026-11-09": entry}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 keys"):
        load_snapshots(path)


def test_load_snapshots_rejects_bad_digest(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    entry = _snapshot_entry(
        sha256={
            name: ("z" * 64 if name == "wind.csv" else "a" * 64) for name in SOURCE_FILES
        }
    )
    payload = {"version": 1, "snapshots": {"2026-11-09": entry}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hexadecimal"):
        load_snapshots(path)


def test_load_snapshots_rejects_negative_row_count(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    entry = _snapshot_entry(
        row_counts={name: (-1 if name == "solar.csv" else 1) for name in SOURCE_FILES}
    )
    payload = {"version": 1, "snapshots": {"2026-11-09": entry}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="non-negative integer"):
        load_snapshots(path)


def test_load_snapshots_rejects_legacy_scope_on_new_date(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    entry = _snapshot_entry(export_scope="legacy_mixed_filters", cdc_baseline=False)
    payload = {"version": 1, "snapshots": {"2026-12-01": entry}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="only allowed for snapshot"):
        load_snapshots(path)


def test_load_snapshots_rejects_missing_export_scope(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    entry = _snapshot_entry()
    del entry["export_scope"]
    payload = {"version": 1, "snapshots": {"2026-11-09": entry}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="export_scope"):
        load_snapshots(path)
