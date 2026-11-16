"""Unit tests for snapshot discovery and orchestration (mocked GCS)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mastr_data_pipeline.checksums import SOURCE_FILES, sha256_file
from mastr_data_pipeline.config import Settings
from mastr_data_pipeline.gcs_bronze import UploadResult
from mastr_data_pipeline.ingest import ingest_snapshot, list_snapshot_files


def _make_snapshot(raw_dir: Path, snapshot_date: str) -> dict[str, Path]:
    folder = raw_dir / snapshot_date
    folder.mkdir(parents=True)
    paths = {}
    for name in SOURCE_FILES:
        path = folder / name
        path.write_bytes(f"{name}\n".encode())
        paths[name] = path
    return paths


def test_list_snapshot_files_ok(tmp_path: Path):
    paths = _make_snapshot(tmp_path, "2026-11-09")
    found = list_snapshot_files(tmp_path, "2026-11-09")
    assert set(found) == set(SOURCE_FILES)
    assert found["wind.csv"] == paths["wind.csv"]


def test_list_snapshot_files_missing_folder(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Snapshot folder not found"):
        list_snapshot_files(tmp_path, "2026-11-09")


def test_list_snapshot_files_missing_csv(tmp_path: Path):
    folder = tmp_path / "2026-11-09"
    folder.mkdir()
    (folder / "wind.csv").write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="Missing CSV"):
        list_snapshot_files(tmp_path, "2026-11-09")


def test_ingest_snapshot_calls_upload_for_each_file(tmp_path: Path):
    paths = _make_snapshot(tmp_path, "2026-11-09")
    settings = Settings(
        project_id="test-project",
        bucket="test-bucket",
        raw_dir=tmp_path,
        bq_dataset="mastr_raw",
        bq_location="europe-west3",
    )

    fake_results = []

    def fake_upload_csv(**kwargs):
        name = kwargs["source_file"]
        result = UploadResult(
            source_file=name,
            snapshot_date="2026-11-09",
            local_path=str(kwargs["local_path"]),
            gs_uri=f"gs://test-bucket/bronze/mastr/snapshot_date=2026-11-09/{name}",
            sha256=sha256_file(paths[name]),
            status="uploaded",
        )
        fake_results.append(result)
        return result

    with patch(
        "mastr_data_pipeline.data_contract.validate_snapshot_contract",
        return_value=None,
    ), patch(
        "mastr_data_pipeline.ingest.expected_checksums",
        return_value={name: sha256_file(path) for name, path in paths.items()},
    ), patch(
        "mastr_data_pipeline.ingest.upload_csv",
        side_effect=fake_upload_csv,
    ) as mocked_upload:
        results = ingest_snapshot(
            "2026-11-09",
            settings=settings,
            client=MagicMock(),
        )

    assert len(results) == 4
    assert mocked_upload.call_count == 4
    assert {r.source_file for r in results} == set(SOURCE_FILES)


def test_get_settings_requires_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.delenv("MASTR_RAW_DIR", raising=False)
    monkeypatch.delenv("BQ_DATASET", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    from mastr_data_pipeline.config import get_settings

    with pytest.raises(ValueError, match="Missing required environment variable"):
        get_settings()


def test_get_settings_reads_required_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("GCS_BUCKET", "bucket")
    monkeypatch.setenv("MASTR_RAW_DIR", str(tmp_path))
    monkeypatch.setenv("BQ_DATASET", "mastr_raw")
    monkeypatch.setenv("BQ_LOCATION", "europe-west3")
    from mastr_data_pipeline.config import get_settings

    settings = get_settings()
    assert settings.project_id == "proj"
    assert settings.bucket == "bucket"
    assert settings.raw_dir == tmp_path
    assert settings.bq_dataset == "mastr_raw"
    assert settings.bq_location == "europe-west3"


def test_get_settings_requires_bq_and_raw_dir(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("GCS_BUCKET", "bucket")
    monkeypatch.delenv("MASTR_RAW_DIR", raising=False)
    monkeypatch.delenv("BQ_DATASET", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    from mastr_data_pipeline.config import get_settings

    with pytest.raises(ValueError, match="MASTR_RAW_DIR"):
        get_settings()


def test_cli_main_invokes_ingest(monkeypatch: pytest.MonkeyPatch):
    from mastr_data_pipeline.__main__ import main

    called = {}

    def fake_ingest(snapshot_date: str):
        called["snapshot_date"] = snapshot_date
        return [
            UploadResult(
                source_file="wind.csv",
                snapshot_date=snapshot_date,
                local_path="/tmp/wind.csv",
                gs_uri="gs://b/bronze/mastr/snapshot_date=2026-11-09/wind.csv",
                sha256="abc",
                status="uploaded",
            )
        ]

    monkeypatch.setattr(
        "mastr_data_pipeline.ingest.ingest_snapshot", fake_ingest
    )
    assert main(["ingest-bronze", "--snapshot-date", "2026-11-09"]) == 0
    assert called["snapshot_date"] == "2026-11-09"
    # Legacy flag-only form still maps to ingest-bronze.
    called.clear()
    assert main(["--snapshot-date", "2026-11-09"]) == 0
    assert called["snapshot_date"] == "2026-11-09"


def test_cli_load_raw(monkeypatch: pytest.MonkeyPatch):
    from mastr_data_pipeline.__main__ import main
    from mastr_data_pipeline.bq_raw import RawLoadResult

    called = {}

    def fake_load(snapshot_date: str, keep_staging: bool = False, **kwargs):
        called["snapshot_date"] = snapshot_date
        called["keep_staging"] = keep_staging
        return RawLoadResult(
            snapshot_date=snapshot_date,
            staging_table="stg",
            destination_table=(
                "proj.mastr_raw.{raw_mastr_wind,raw_mastr_solar,"
                "raw_mastr_biomass,raw_mastr_storage}"
            ),
            row_counts={"wind.csv": 278},
            ingested_at="2026-11-15T00:00:00+00:00",
            status="replaced",
            destination_tables=(
                "proj.mastr_raw.raw_mastr_wind",
                "proj.mastr_raw.raw_mastr_solar",
                "proj.mastr_raw.raw_mastr_biomass",
                "proj.mastr_raw.raw_mastr_storage",
            ),
        )

    monkeypatch.setattr(
        "mastr_data_pipeline.load_raw.load_raw_snapshot", fake_load
    )
    assert main(["load-raw", "--snapshot-date", "2026-11-09"]) == 0
    assert called == {"snapshot_date": "2026-11-09", "keep_staging": False}
