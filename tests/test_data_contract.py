"""Unit tests for MaStR Data Contract validation (no GCS / BigQuery)."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from mastr_data_pipeline.checksums import sha256_file
from mastr_data_pipeline.config_loader import SOURCE_FILES, load_german_headers
from mastr_data_pipeline.data_contract import (
    DataContractError,
    validate_snapshot_contract,
)
from mastr_data_pipeline.raw_schema import GERMAN_HEADERS as SCHEMA_HEADERS

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_NOV9 = REPO_ROOT / "data" / "raw" / "2026-11-09"
REAL_NOV16 = REPO_ROOT / "data" / "raw" / "2026-11-16"
HEADERS = load_german_headers()


def _write_snapshots(path: Path, snapshots: dict) -> Path:
    path.write_text(
        json.dumps({"version": 1, "snapshots": snapshots}, indent=2),
        encoding="utf-8",
    )
    return path


def _base_row(*, unit_id: str, energy: str, status: str = "In Betrieb") -> dict[str, str]:
    row = {h: "" for h in HEADERS}
    row["MaStR-Nr. der Einheit"] = unit_id
    row["Energieträger"] = energy
    row["Betriebs-Status"] = status
    row["Landkreis"] = "Potsdam-Mittelmark"
    row["Bundesland"] = "Brandenburg"
    row["Nettonennleistung der Einheit"] = "10"
    row["Bruttoleistung der Einheit"] = "10"
    row["Registrierungsdatum der Einheit"] = "11/02/2019"
    return row


def _write_source_csv(path: Path, rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(HEADERS),
            delimiter=";",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return sha256_file(path)


ENERGY = {
    "wind.csv": "Wind",
    "solar.csv": "Solare Strahlungsenergie",
    "biomass.csv": "Biomasse",
    "battery.csv": "Speicher",
}


def _build_valid_snapshot(folder: Path, *, prefix: str = "SEE") -> dict[str, dict]:
    """Create four minimal valid CSVs and return row_counts + sha256 maps."""
    row_counts: dict[str, int] = {}
    digests: dict[str, str] = {}
    for idx, name in enumerate(SOURCE_FILES):
        rows = [
            _base_row(
                unit_id=f"{prefix}{idx}000000000001",
                energy=ENERGY[name],
            )
        ]
        digest = _write_source_csv(folder / name, rows)
        row_counts[name] = 1
        digests[name] = digest
    return {"row_counts": row_counts, "sha256": digests}


@pytest.mark.skipif(not REAL_NOV9.is_dir(), reason="Nov 9 local CSVs not present")
def test_accepts_nov9_legacy_snapshot(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    shutil.copytree(REAL_NOV9, raw_dir / "2026-11-09")
    # Use repo snapshots.json (registered legacy entry).
    result = validate_snapshot_contract("2026-11-09", raw_dir)
    assert result.status == "passed"
    assert result.export_scope == "legacy_mixed_filters"
    assert result.cdc_baseline is False
    assert sum(result.row_counts.values()) == 32611


@pytest.mark.skipif(not REAL_NOV16.is_dir(), reason="Nov 16 local CSVs not present")
def test_accepts_nov16_all_statuses_baseline(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    shutil.copytree(REAL_NOV16, raw_dir / "2026-11-16")
    result = validate_snapshot_contract("2026-11-16", raw_dir)
    assert result.status == "passed"
    assert result.export_scope == "all_statuses"
    assert result.cdc_baseline is True
    assert result.row_counts == {
        "wind.csv": 278,
        "solar.csv": 21631,
        "biomass.csv": 58,
        "battery.csv": 11676,
    }
    assert sum(result.row_counts.values()) == 33643


def test_rejects_missing_csv(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    (folder / "wind.csv").unlink()
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="missing|Missing CSV"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_extra_csv(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    (folder / "extra.csv").write_text("a;b\n1;2\n", encoding="utf-8")
    # Non-CSV should be ignored
    (folder / "readme.txt").write_text("ok", encoding="utf-8")
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="unexpected CSV"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_ignores_non_csv_sidecar(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    (folder / "notes.txt").write_text("ignored", encoding="utf-8")
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    result = validate_snapshot_contract(
        "2026-12-01", tmp_path / "raw", snapshots_path=snaps
    )
    assert result.status == "passed"


def test_rejects_wrong_energy_carrier(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    # Overwrite wind with solar carrier
    bad = [_base_row(unit_id="SEE999000000000001", energy="Solare Strahlungsenergie")]
    meta["sha256"]["wind.csv"] = _write_source_csv(folder / "wind.csv", bad)
    meta["row_counts"]["wind.csv"] = 1
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="Energieträger"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_wrong_schema_columns(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    path = folder / "wind.csv"
    path.write_text("col_a;col_b\n1;2\n", encoding="utf-8-sig")
    meta["sha256"]["wind.csv"] = sha256_file(path)
    meta["row_counts"]["wind.csv"] = 1
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="column headers|delimiter"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_missing_and_duplicate_ids(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)

    blank = [_base_row(unit_id="", energy="Wind")]
    meta["sha256"]["wind.csv"] = _write_source_csv(folder / "wind.csv", blank)
    meta["row_counts"]["wind.csv"] = 1
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="missing installation ID"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)

    # Duplicate within file
    dup_rows = [
        _base_row(unit_id="SEEDUP000000000001", energy="Wind"),
        _base_row(unit_id="SEEDUP000000000001", energy="Wind"),
    ]
    meta["sha256"]["wind.csv"] = _write_source_csv(folder / "wind.csv", dup_rows)
    meta["row_counts"]["wind.csv"] = 2
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="duplicate installation IDs within"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_cross_file_duplicate_ids(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    shared = "SEESHARED000000001"
    meta["sha256"]["wind.csv"] = _write_source_csv(
        folder / "wind.csv",
        [_base_row(unit_id=shared, energy="Wind")],
    )
    meta["sha256"]["solar.csv"] = _write_source_csv(
        folder / "solar.csv",
        [_base_row(unit_id=shared, energy="Solare Strahlungsenergie")],
    )
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="across source files"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_wrong_geography(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    row = _base_row(unit_id="SEEGEO000000000001", energy="Wind")
    row["Landkreis"] = "Berlin"
    meta["sha256"]["wind.csv"] = _write_source_csv(folder / "wind.csv", [row])
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="geography"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_checksum_mismatch(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    meta["sha256"]["wind.csv"] = "0" * 64
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="SHA-256 mismatch"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_status_seed_includes_temporarily_decommissioned():
    seed = (REPO_ROOT / "dbt" / "seeds" / "seed_statuses.csv").read_text(encoding="utf-8")
    assert "temporarily_decommissioned" in seed
    assert "5,temporarily_decommissioned,Temporarily decommissioned,false" in seed
    macro = (
        REPO_ROOT / "dbt" / "macros" / "select_stg_mastr_units.sql"
    ).read_text(encoding="utf-8")
    assert "Vorübergehend stillgelegt" in macro
    assert "temporarily_decommissioned" in macro


def test_rejects_row_count_mismatch(tmp_path: Path):
    folder = tmp_path / "raw" / "2026-12-01"
    meta = _build_valid_snapshot(folder)
    meta["row_counts"]["wind.csv"] = 99
    snaps = tmp_path / "snapshots.json"
    _write_snapshots(
        snaps,
        {
            "2026-12-01": {
                "export_scope": "all_statuses",
                "cdc_baseline": True,
                **meta,
            }
        },
    )
    with pytest.raises(DataContractError, match="row count mismatch"):
        validate_snapshot_contract("2026-12-01", tmp_path / "raw", snapshots_path=snaps)


def test_rejects_unregistered_snapshot(tmp_path: Path):
    folder = tmp_path / "raw" / "2099-01-01"
    _build_valid_snapshot(folder)
    with pytest.raises(DataContractError, match="not registered"):
        validate_snapshot_contract("2099-01-01", tmp_path / "raw")


def test_headers_constant_alignment():
    assert HEADERS == SCHEMA_HEADERS
    assert len(HEADERS) == 64
