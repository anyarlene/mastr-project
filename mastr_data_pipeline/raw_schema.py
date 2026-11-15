"""Explicit BigQuery Raw schema for MaStR CSVs (all payload fields STRING)."""

from __future__ import annotations

import re
from functools import lru_cache

from mastr_data_pipeline.config_loader import load_german_headers, load_snapshots

# German header order as exported (64 columns). Positional mapping for loads.
GERMAN_HEADERS: tuple[str, ...] = load_german_headers()

_UMLAUT_MAP = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
)


def sanitize_field_name(german_header: str) -> str:
    """Convert a German MaStR header to a BigQuery-safe snake_case name."""
    text = german_header.translate(_UMLAUT_MAP)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_").lower()


@lru_cache(maxsize=1)
def payload_field_names() -> tuple[str, ...]:
    names = tuple(sanitize_field_name(h) for h in GERMAN_HEADERS)
    if len(names) != 64:
        raise ValueError(f"Expected 64 payload fields, got {len(names)}")
    if len(set(names)) != len(names):
        raise ValueError("Sanitized payload field names are not unique")
    return names


# Installation unit natural key in Raw (sanitized German header).
UNIT_ID_FIELD = sanitize_field_name("MaStR-Nr. der Einheit")

LINEAGE_FIELDS: tuple[str, ...] = (
    "source_file",
    "snapshot_date",
    "ingested_at",
)

# Snapshot-specific expected row counts (data rows, excluding header).
EXPECTED_ROW_COUNTS: dict[str, dict[str, int]] = {
    snapshot_date: dict(entry["row_counts"])
    for snapshot_date, entry in load_snapshots().items()
}


def expected_row_counts(snapshot_date: str) -> dict[str, int]:
    try:
        return dict(EXPECTED_ROW_COUNTS[snapshot_date])
    except KeyError as exc:
        known = ", ".join(sorted(EXPECTED_ROW_COUNTS)) or "(none)"
        raise ValueError(
            f"No expected row counts for snapshot_date={snapshot_date!r}. "
            f"Known snapshots: {known}"
        ) from exc


def payload_schema_fields() -> list[dict[str, str]]:
    """BigQuery schema dicts for the 64 STRING payload columns."""
    return [{"name": name, "type": "STRING", "mode": "NULLABLE"} for name in payload_field_names()]


def raw_table_schema_fields() -> list[dict[str, str]]:
    """Full Raw table schema: payload STRING columns + lineage."""
    return [
        *payload_schema_fields(),
        {"name": "source_file", "type": "STRING", "mode": "REQUIRED"},
        {"name": "snapshot_date", "type": "DATE", "mode": "REQUIRED"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
