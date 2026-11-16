"""Generate dbt seed rows for snapshot expectations from config/snapshots.json.

config/snapshots.json is the single source of truth for expected row counts,
SHA-256 checksums, and export_scope. This module projects those values into
CSV seeds for dbt completeness and CDC eligibility — it does not duplicate
business logic beyond that projection.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from mastr_data_pipeline.config_loader import SOURCE_FILES, load_json, load_snapshots

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOTS_PATH = REPO_ROOT / "config" / "snapshots.json"
DEFAULT_SEED_PATH = REPO_ROOT / "dbt" / "seeds" / "seed_snapshot_expectations.csv"
DEFAULT_METADATA_SEED_PATH = (
    REPO_ROOT / "dbt" / "seeds" / "seed_snapshot_metadata.csv"
)

SEED_FIELDNAMES = ("snapshot_date", "source_file", "expected_row_count")
METADATA_SEED_FIELDNAMES = ("snapshot_date", "export_scope", "cdc_baseline")


def expectation_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build deterministic seed rows from a snapshots.json payload.

    Rows are ordered by snapshot_date ascending, then SOURCE_FILES order.
    """
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, dict) or not snapshots:
        raise ValueError("snapshots.json must contain a non-empty 'snapshots' object")

    rows: list[dict[str, Any]] = []
    for snapshot_date in sorted(snapshots):
        entry = snapshots[snapshot_date]
        if not isinstance(entry, dict):
            raise ValueError(f"snapshot {snapshot_date!r} must be an object")
        row_counts = entry.get("row_counts")
        if not isinstance(row_counts, dict):
            raise ValueError(f"snapshot {snapshot_date!r} must include row_counts")
        missing = [name for name in SOURCE_FILES if name not in row_counts]
        if missing:
            raise ValueError(
                f"snapshot {snapshot_date!r} missing row_counts for: {missing}"
            )
        for source_file in SOURCE_FILES:
            count = row_counts[source_file]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(
                    f"snapshot {snapshot_date!r} row_counts[{source_file!r}] "
                    "must be a non-negative integer"
                )
            rows.append(
                {
                    "snapshot_date": snapshot_date,
                    "source_file": source_file,
                    "expected_row_count": count,
                }
            )
    return rows


def metadata_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build deterministic snapshot metadata seed rows.

    Uses load_snapshots validation rules via a temp round-trip on the payload
    structure already present in snapshots.json.
    """
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, dict) or not snapshots:
        raise ValueError("snapshots.json must contain a non-empty 'snapshots' object")

    # Validate through the same loader contract by writing a temp-less check:
    # require export_scope / cdc_baseline fields matching load_snapshots rules.
    rows: list[dict[str, Any]] = []
    for snapshot_date in sorted(snapshots):
        entry = snapshots[snapshot_date]
        if not isinstance(entry, dict):
            raise ValueError(f"snapshot {snapshot_date!r} must be an object")
        export_scope = entry.get("export_scope")
        cdc_baseline = entry.get("cdc_baseline")
        if not isinstance(export_scope, str) or not export_scope:
            raise ValueError(f"snapshot {snapshot_date!r} must include export_scope")
        if not isinstance(cdc_baseline, bool):
            raise ValueError(f"snapshot {snapshot_date!r} cdc_baseline must be a boolean")
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "export_scope": export_scope,
                "cdc_baseline": "true" if cdc_baseline else "false",
            }
        )
    return rows


def write_snapshot_expectations_seed(
    snapshots_path: Path | None = None,
    seed_path: Path | None = None,
) -> Path:
    """Read snapshots.json and write seed_snapshot_expectations.csv."""
    src = snapshots_path or DEFAULT_SNAPSHOTS_PATH
    dest = seed_path or DEFAULT_SEED_PATH
    payload = load_json(src)
    rows = expectation_rows_from_payload(payload)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return dest


def write_snapshot_metadata_seed(
    snapshots_path: Path | None = None,
    seed_path: Path | None = None,
) -> Path:
    """Read snapshots.json and write seed_snapshot_metadata.csv."""
    src = snapshots_path or DEFAULT_SNAPSHOTS_PATH
    dest = seed_path or DEFAULT_METADATA_SEED_PATH
    # Ensure payload satisfies loader rules before projecting.
    load_snapshots(src)
    payload = load_json(src)
    rows = metadata_rows_from_payload(payload)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=METADATA_SEED_FIELDNAMES,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return dest


def write_all_snapshot_seeds(
    snapshots_path: Path | None = None,
    expectations_seed_path: Path | None = None,
    metadata_seed_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write expectations + metadata seeds from snapshots.json."""
    expectations = write_snapshot_expectations_seed(
        snapshots_path=snapshots_path,
        seed_path=expectations_seed_path,
    )
    metadata = write_snapshot_metadata_seed(
        snapshots_path=snapshots_path,
        seed_path=metadata_seed_path,
    )
    return expectations, metadata


def read_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    """Read an expectations seed CSV into typed row dicts."""
    with seed_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(SEED_FIELDNAMES):
            raise ValueError(
                f"{seed_path}: expected header {SEED_FIELDNAMES}, got {reader.fieldnames}"
            )
        rows: list[dict[str, Any]] = []
        for row in reader:
            rows.append(
                {
                    "snapshot_date": row["snapshot_date"],
                    "source_file": row["source_file"],
                    "expected_row_count": int(row["expected_row_count"]),
                }
            )
        return rows


def read_metadata_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    """Read a snapshot metadata seed CSV into typed row dicts."""
    with seed_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(METADATA_SEED_FIELDNAMES):
            raise ValueError(
                f"{seed_path}: expected header {METADATA_SEED_FIELDNAMES}, "
                f"got {reader.fieldnames}"
            )
        rows: list[dict[str, Any]] = []
        for row in reader:
            flag = row["cdc_baseline"].strip().lower()
            if flag not in {"true", "false"}:
                raise ValueError(
                    f"{seed_path}: cdc_baseline must be true/false, got {row['cdc_baseline']!r}"
                )
            rows.append(
                {
                    "snapshot_date": row["snapshot_date"],
                    "export_scope": row["export_scope"],
                    "cdc_baseline": flag == "true",
                }
            )
        return rows
