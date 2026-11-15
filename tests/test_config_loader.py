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
    assert EXPECTED_ROW_COUNTS["2026-11-09"] == snapshots["2026-11-09"]["row_counts"]
    assert EXPECTED_SHA256["2026-11-09"] == snapshots["2026-11-09"]["sha256"]
    assert set(EXPECTED_SHA256["2026-11-09"]) == set(SOURCE_FILES)
    assert expected_checksums("2026-11-09") == EXPECTED_SHA256["2026-11-09"]


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


def test_load_snapshots_rejects_incomplete_sha_keys(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    payload = {
        "version": 1,
        "snapshots": {
            "2026-11-09": {
                "row_counts": {name: 1 for name in SOURCE_FILES},
                "sha256": {name: "a" * 64 for name in SOURCE_FILES if name != "wind.csv"},
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 keys"):
        load_snapshots(path)


def test_load_snapshots_rejects_bad_digest(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    payload = {
        "version": 1,
        "snapshots": {
            "2026-11-09": {
                "row_counts": {name: 1 for name in SOURCE_FILES},
                "sha256": {
                    name: ("z" * 64 if name == "wind.csv" else "a" * 64)
                    for name in SOURCE_FILES
                },
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hexadecimal"):
        load_snapshots(path)


def test_load_snapshots_rejects_negative_row_count(tmp_path: Path):
    path = tmp_path / "snapshots.json"
    payload = {
        "version": 1,
        "snapshots": {
            "2026-11-09": {
                "row_counts": {
                    name: (-1 if name == "solar.csv" else 1) for name in SOURCE_FILES
                },
                "sha256": {name: "a" * 64 for name in SOURCE_FILES},
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="non-negative integer"):
        load_snapshots(path)
