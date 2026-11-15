"""Tests for snapshot expectations seed generation (no dbt / GCP)."""

from __future__ import annotations

import json
from pathlib import Path

from mastr_data_pipeline.config_loader import SOURCE_FILES
from mastr_data_pipeline.snapshot_expectations_seed import (
    DEFAULT_SEED_PATH,
    DEFAULT_SNAPSHOTS_PATH,
    expectation_rows_from_payload,
    read_seed_rows,
    write_snapshot_expectations_seed,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_expectation_rows_match_snapshots_json():
    payload = json.loads(DEFAULT_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    rows = expectation_rows_from_payload(payload)

    assert rows, "expected at least one seed row"
    assert [r["source_file"] for r in rows[:4]] == list(SOURCE_FILES)

    by_snap: dict[str, dict[str, int]] = {}
    for row in rows:
        by_snap.setdefault(row["snapshot_date"], {})[row["source_file"]] = row[
            "expected_row_count"
        ]

    assert set(by_snap) == set(payload["snapshots"])
    for snapshot_date, counts in payload["snapshots"].items():
        assert by_snap[snapshot_date] == counts["row_counts"]


def test_committed_seed_matches_snapshots_json():
    """Committed CSV must stay in sync with config/snapshots.json."""
    assert DEFAULT_SEED_PATH.is_file(), (
        "Missing seed_snapshot_expectations.csv — run "
        "`make generate-snapshot-seed` before dbt seed"
    )
    payload = json.loads(DEFAULT_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    assert read_seed_rows(DEFAULT_SEED_PATH) == expectation_rows_from_payload(payload)


def test_write_seed_is_deterministic(tmp_path: Path):
    payload = json.loads(DEFAULT_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    out_a = tmp_path / "a.csv"
    out_b = tmp_path / "b.csv"
    write_snapshot_expectations_seed(DEFAULT_SNAPSHOTS_PATH, out_a)
    write_snapshot_expectations_seed(DEFAULT_SNAPSHOTS_PATH, out_b)
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    assert read_seed_rows(out_a) == expectation_rows_from_payload(payload)
