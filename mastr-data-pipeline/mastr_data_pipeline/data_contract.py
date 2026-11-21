"""MaStR snapshot Data Contract validation (local CSVs, before Bronze).

``export_scope`` is declared in config/snapshots.json. CSV files alone cannot
prove whether an export included all operational statuses.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from mastr_data_pipeline.checksums import sha256_file, verify_local_checksum
from mastr_data_pipeline.config_loader import (
    EXPECTED_ENERGY_CARRIER_BY_SOURCE,
    EXPORT_SCOPE_ALL_STATUSES,
    EXPORT_SCOPE_LEGACY_MIXED,
    LEGACY_MIXED_FILTERS_SNAPSHOT,
    SOURCE_FILES,
    load_german_headers,
    load_snapshots,
)
from mastr_data_pipeline.ingest import list_snapshot_files, snapshot_dir
from mastr_data_pipeline.raw_schema import GERMAN_HEADERS

UNIT_ID_HEADER = "MaStR-Nr. der Einheit"
ENERGY_HEADER = "Energieträger"
STATUS_HEADER = "Betriebs-Status"
DISTRICT_HEADER = "Landkreis"
STATE_HEADER = "Bundesland"
NET_POWER_HEADER = "Nettonennleistung der Einheit"
GROSS_POWER_HEADER = "Bruttoleistung der Einheit"
STORAGE_CAPACITY_HEADER = "Nutzbare Speicherkapazität in kWh"

EXPECTED_DISTRICT = "Potsdam-Mittelmark"
EXPECTED_STATE = "Brandenburg"

# European decimal (optional sign, digits, optional comma decimals) or blank.
_DECIMAL_RE = re.compile(r"^-?\d+(,\d+)?$")
# MaStR calendar dates as used in exports (DD/MM/YYYY).
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_DATE_HEADERS = (
    "Inbetriebnahmedatum der Einheit",
    "Inbetriebnahmedatum der Einheit am aktuellen Standort",
    "Registrierungsdatum der Einheit",
    "Datum der endgültigen Stilllegung",
    "Datum der geplanten Inbetriebnahme",
    "Inbetriebnahmedatum der EEG-Anlage",
    "Inbetriebnahmedatum der KWK-Anlage",
)


@dataclass
class DataContractResult:
    snapshot_date: str
    export_scope: str
    cdc_baseline: bool
    row_counts: dict[str, int] = field(default_factory=dict)
    sha256: dict[str, str] = field(default_factory=dict)
    status: str = "passed"


class DataContractError(ValueError):
    """Raised when a snapshot violates the MaStR Data Contract."""


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a MaStR CSV with UTF-8 BOM support and semicolon delimiter."""
    raw = path.read_bytes()
    if not raw:
        raise DataContractError(f"{path.name}: file is empty")
    # Reject UTF-16 / obvious non-UTF8 by requiring successful utf-8-sig decode.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataContractError(
            f"{path.name}: encoding must be UTF-8 (BOM optional); decode failed"
        ) from exc

    # Sniff first line delimiter: require semicolon-separated header.
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if first_line.count(";") < 10:
        raise DataContractError(
            f"{path.name}: expected semicolon (';') delimiter with 64 columns"
        )

    reader = csv.DictReader(text.splitlines(), delimiter=";")
    if reader.fieldnames is None:
        raise DataContractError(f"{path.name}: missing CSV header")
    columns = list(reader.fieldnames)
    rows = list(reader)
    return columns, rows


def _validate_folder_files(folder: Path) -> None:
    """Require exactly the four SOURCE_FILES CSVs; ignore non-CSV files."""
    if not folder.is_dir():
        raise DataContractError(f"Snapshot folder not found: {folder}")

    csv_names = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
    expected = list(SOURCE_FILES)
    missing = [name for name in expected if name not in csv_names]
    unexpected = [name for name in csv_names if name not in expected]
    if missing or unexpected:
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if unexpected:
            parts.append(f"unexpected CSV(s) {unexpected}")
        raise DataContractError(
            f"{folder}: exactly {expected} required; {'; '.join(parts)}"
        )


def _validate_numeric(value: str, *, field_name: str, path_name: str, row_num: int) -> None:
    text = (value or "").strip()
    if text == "":
        return
    if not _DECIMAL_RE.match(text):
        raise DataContractError(
            f"{path_name} row {row_num}: invalid {field_name}={value!r} "
            "(expected European decimal or blank)"
        )


def _validate_date(value: str, *, field_name: str, path_name: str, row_num: int) -> None:
    text = (value or "").strip()
    if text == "":
        return
    if not _DATE_RE.match(text):
        raise DataContractError(
            f"{path_name} row {row_num}: invalid {field_name}={value!r} "
            "(expected DD/MM/YYYY or blank)"
        )


def validate_snapshot_contract(
    snapshot_date: str,
    raw_dir: Path,
    *,
    snapshots_path: Path | None = None,
) -> DataContractResult:
    """
    Validate a local snapshot folder against the MaStR Data Contract.

    Does not modify CSV contents. Raises DataContractError on failure.
    """
    snapshots = load_snapshots(snapshots_path)
    if snapshot_date not in snapshots:
        known = ", ".join(sorted(snapshots)) or "(none)"
        raise DataContractError(
            f"snapshot_date {snapshot_date!r} is not registered in snapshots.json. "
            f"Known: {known}"
        )

    meta = snapshots[snapshot_date]
    export_scope = meta["export_scope"]
    cdc_baseline = bool(meta["cdc_baseline"])

    if export_scope == EXPORT_SCOPE_LEGACY_MIXED:
        if snapshot_date != LEGACY_MIXED_FILTERS_SNAPSHOT:
            raise DataContractError(
                f"export_scope {EXPORT_SCOPE_LEGACY_MIXED!r} is only accepted for "
                f"{LEGACY_MIXED_FILTERS_SNAPSHOT}"
            )
    elif export_scope != EXPORT_SCOPE_ALL_STATUSES:
        raise DataContractError(
            f"invalid export_scope {export_scope!r}; "
            f"new snapshots must use {EXPORT_SCOPE_ALL_STATUSES!r}"
        )

    folder = snapshot_dir(raw_dir, snapshot_date)
    _validate_folder_files(folder)
    paths = list_snapshot_files(raw_dir, snapshot_date)

    headers = load_german_headers()
    if headers != GERMAN_HEADERS:
        raise DataContractError("Loaded German headers do not match GERMAN_HEADERS constant")

    expected_counts: dict[str, int] = meta["row_counts"]
    expected_sha: dict[str, str] = meta["sha256"]
    actual_counts: dict[str, int] = {}
    actual_sha: dict[str, str] = {}
    all_unit_ids: list[str] = []

    for source_file in SOURCE_FILES:
        path = paths[source_file]
        try:
            digest = verify_local_checksum(path, expected_sha[source_file])
        except ValueError as exc:
            raise DataContractError(str(exc)) from exc
        actual_sha[source_file] = digest

        columns, rows = _read_csv_rows(path)
        if columns != list(headers):
            raise DataContractError(
                f"{source_file}: column headers must match the 64 German MaStR columns "
                "in order (see config/mastr_headers.json)"
            )

        if len(rows) != expected_counts[source_file]:
            raise DataContractError(
                f"{source_file}: row count mismatch: expected "
                f"{expected_counts[source_file]}, got {len(rows)}"
            )
        actual_counts[source_file] = len(rows)

        expected_energy = EXPECTED_ENERGY_CARRIER_BY_SOURCE[source_file]
        unit_ids: list[str] = []
        for idx, row in enumerate(rows, start=2):  # header is line 1
            unit_id = (row.get(UNIT_ID_HEADER) or "").strip()
            if not unit_id:
                raise DataContractError(
                    f"{source_file} row {idx}: missing installation ID "
                    f"({UNIT_ID_HEADER})"
                )
            unit_ids.append(unit_id)

            energy = (row.get(ENERGY_HEADER) or "").strip()
            if energy != expected_energy:
                raise DataContractError(
                    f"{source_file} row {idx}: expected {ENERGY_HEADER}="
                    f"{expected_energy!r}, got {energy!r}"
                )

            district = (row.get(DISTRICT_HEADER) or "").strip()
            state = (row.get(STATE_HEADER) or "").strip()
            if district != EXPECTED_DISTRICT or state != EXPECTED_STATE:
                raise DataContractError(
                    f"{source_file} row {idx}: geography must be "
                    f"{EXPECTED_DISTRICT}, {EXPECTED_STATE}; "
                    f"got {district!r}, {state!r}"
                )

            status = (row.get(STATUS_HEADER) or "").strip()
            if not status:
                raise DataContractError(
                    f"{source_file} row {idx}: missing {STATUS_HEADER}"
                )

            _validate_numeric(
                row.get(NET_POWER_HEADER, ""),
                field_name=NET_POWER_HEADER,
                path_name=source_file,
                row_num=idx,
            )
            _validate_numeric(
                row.get(GROSS_POWER_HEADER, ""),
                field_name=GROSS_POWER_HEADER,
                path_name=source_file,
                row_num=idx,
            )
            _validate_numeric(
                row.get(STORAGE_CAPACITY_HEADER, ""),
                field_name=STORAGE_CAPACITY_HEADER,
                path_name=source_file,
                row_num=idx,
            )
            for date_header in _DATE_HEADERS:
                _validate_date(
                    row.get(date_header, ""),
                    field_name=date_header,
                    path_name=source_file,
                    row_num=idx,
                )

        dupes = [uid for uid, n in Counter(unit_ids).items() if n > 1]
        if dupes:
            raise DataContractError(
                f"{source_file}: duplicate installation IDs within file: "
                f"{dupes[:5]}{'…' if len(dupes) > 5 else ''}"
            )
        all_unit_ids.extend(unit_ids)

    cross_dupes = [uid for uid, n in Counter(all_unit_ids).items() if n > 1]
    if cross_dupes:
        raise DataContractError(
            f"duplicate installation IDs across source files: "
            f"{cross_dupes[:5]}{'…' if len(cross_dupes) > 5 else ''}"
        )

    return DataContractResult(
        snapshot_date=snapshot_date,
        export_scope=export_scope,
        cdc_baseline=cdc_baseline,
        row_counts=actual_counts,
        sha256=actual_sha,
        status="passed",
    )
