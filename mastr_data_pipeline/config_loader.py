"""Load MaStR configuration from JSON files under config/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SOURCE_FILES: tuple[str, ...] = (
    "wind.csv",
    "solar.csv",
    "biomass.csv",
    "battery.csv",
)

# Declared snapshot export scope (metadata — not a CSV column).
EXPORT_SCOPE_ALL_STATUSES = "all_statuses"
EXPORT_SCOPE_LEGACY_MIXED = "legacy_mixed_filters"
ALLOWED_EXPORT_SCOPES: frozenset[str] = frozenset(
    {
        EXPORT_SCOPE_ALL_STATUSES,
        EXPORT_SCOPE_LEGACY_MIXED,
    }
)
# Only this historical snapshot may use legacy_mixed_filters.
LEGACY_MIXED_FILTERS_SNAPSHOT = "2026-11-09"

# Expected Energieträger value per required source file.
EXPECTED_ENERGY_CARRIER_BY_SOURCE: dict[str, str] = {
    "wind.csv": "Wind",
    "solar.csv": "Solare Strahlungsenergie",
    "biomass.csv": "Biomasse",
    "battery.csv": "Speicher",
}

# BigQuery Raw table per Bronze CSV (split Raw architecture).
RAW_TABLE_BY_SOURCE: dict[str, str] = {
    "wind.csv": "raw_mastr_wind",
    "solar.csv": "raw_mastr_solar",
    "biomass.csv": "raw_mastr_biomass",
    "battery.csv": "raw_mastr_storage",
}

RAW_TABLES: tuple[str, ...] = tuple(RAW_TABLE_BY_SOURCE[f] for f in SOURCE_FILES)

_REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = _REPO_ROOT / "config"


def config_dir() -> Path:
    return CONFIG_DIR


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_german_headers(path: Path | None = None) -> tuple[str, ...]:
    """Load the ordered German CSV headers from mastr_headers.json."""
    headers_path = path or (config_dir() / "mastr_headers.json")
    payload = load_json(headers_path)
    columns = payload.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(f"{headers_path}: 'columns' must be a non-empty list")
    if not all(isinstance(col, str) and col.strip() for col in columns):
        raise ValueError(f"{headers_path}: every column must be a non-empty string")
    if len(columns) != 64:
        raise ValueError(f"{headers_path}: expected 64 columns, got {len(columns)}")
    if len(set(columns)) != len(columns):
        raise ValueError(f"{headers_path}: duplicate column names are not allowed")
    return tuple(columns)


def load_snapshots(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """
    Load snapshot metadata from snapshots.json.

    Returns a mapping of snapshot_date -> {
      export_scope, cdc_baseline, notes?, row_counts, sha256
    }.

    ``export_scope`` is user-declared metadata (not present in MaStR CSVs).
    """
    snapshots_path = path or (config_dir() / "snapshots.json")
    payload = load_json(snapshots_path)
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, dict) or not snapshots:
        raise ValueError(f"{snapshots_path}: 'snapshots' must be a non-empty object")

    validated: dict[str, dict[str, Any]] = {}
    expected_files = set(SOURCE_FILES)

    for snapshot_date, entry in snapshots.items():
        if not isinstance(snapshot_date, str) or not snapshot_date.strip():
            raise ValueError(f"{snapshots_path}: snapshot dates must be non-empty strings")
        if not isinstance(entry, dict):
            raise ValueError(f"{snapshots_path}: snapshot '{snapshot_date}' must be an object")

        export_scope = entry.get("export_scope")
        if not isinstance(export_scope, str) or export_scope not in ALLOWED_EXPORT_SCOPES:
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' export_scope must be one of "
                f"{sorted(ALLOWED_EXPORT_SCOPES)}"
            )
        if (
            export_scope == EXPORT_SCOPE_LEGACY_MIXED
            and snapshot_date != LEGACY_MIXED_FILTERS_SNAPSHOT
        ):
            raise ValueError(
                f"{snapshots_path}: export_scope '{EXPORT_SCOPE_LEGACY_MIXED}' is only "
                f"allowed for snapshot '{LEGACY_MIXED_FILTERS_SNAPSHOT}' "
                f"(got '{snapshot_date}')"
            )
        if (
            snapshot_date != LEGACY_MIXED_FILTERS_SNAPSHOT
            and export_scope != EXPORT_SCOPE_ALL_STATUSES
        ):
            raise ValueError(
                f"{snapshots_path}: new snapshots must use export_scope "
                f"'{EXPORT_SCOPE_ALL_STATUSES}' (CDC-eligible). "
                f"Got '{export_scope}' for '{snapshot_date}'."
            )

        cdc_baseline = entry.get("cdc_baseline", export_scope == EXPORT_SCOPE_ALL_STATUSES)
        if not isinstance(cdc_baseline, bool):
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' cdc_baseline must be a boolean"
            )
        if cdc_baseline and export_scope != EXPORT_SCOPE_ALL_STATUSES:
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' cannot be cdc_baseline "
                f"unless export_scope is '{EXPORT_SCOPE_ALL_STATUSES}'"
            )

        row_counts = entry.get("row_counts")
        sha256 = entry.get("sha256")
        if not isinstance(row_counts, dict) or not isinstance(sha256, dict):
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' needs "
                "'row_counts' and 'sha256' objects"
            )

        if set(row_counts) != expected_files:
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' row_counts keys "
                f"must be exactly {SOURCE_FILES}"
            )
        if set(sha256) != expected_files:
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' sha256 keys "
                f"must be exactly {SOURCE_FILES}"
            )

        normalized_counts: dict[str, int] = {}
        for filename in SOURCE_FILES:
            count = row_counts[filename]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(
                    f"{snapshots_path}: snapshot '{snapshot_date}' "
                    f"row_counts['{filename}'] must be a non-negative integer"
                )
            normalized_counts[filename] = count

        normalized_sha: dict[str, str] = {}
        for filename in SOURCE_FILES:
            digest = sha256[filename]
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(
                    f"{snapshots_path}: snapshot '{snapshot_date}' "
                    f"sha256['{filename}'] must be a 64-character hex string"
                )
            try:
                int(digest, 16)
            except ValueError as exc:
                raise ValueError(
                    f"{snapshots_path}: snapshot '{snapshot_date}' "
                    f"sha256['{filename}'] must be hexadecimal"
                ) from exc
            normalized_sha[filename] = digest.lower()

        notes = entry.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ValueError(
                f"{snapshots_path}: snapshot '{snapshot_date}' notes must be a string"
            )

        validated[snapshot_date] = {
            "export_scope": export_scope,
            "cdc_baseline": cdc_baseline,
            "row_counts": normalized_counts,
            "sha256": normalized_sha,
        }
        if isinstance(notes, str):
            validated[snapshot_date]["notes"] = notes

    return validated
