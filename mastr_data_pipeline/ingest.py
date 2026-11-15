"""Orchestrate MaStR snapshot upload to GCS Bronze."""

from __future__ import annotations

from pathlib import Path

from google.cloud import storage

from mastr_data_pipeline.checksums import SOURCE_FILES, expected_checksums
from mastr_data_pipeline.config import Settings, get_settings
from mastr_data_pipeline.gcs_bronze import UploadResult, upload_csv


def snapshot_dir(raw_dir: Path, snapshot_date: str) -> Path:
    """Return data/raw/<snapshot_date>/ for the dated folder label."""
    return raw_dir / snapshot_date


def list_snapshot_files(raw_dir: Path, snapshot_date: str) -> dict[str, Path]:
    """Locate the four expected CSVs for a snapshot folder label."""
    folder = snapshot_dir(raw_dir, snapshot_date)
    if not folder.is_dir():
        raise FileNotFoundError(
            f"Snapshot folder not found for snapshot_date={snapshot_date!r}: {folder}"
        )

    paths: dict[str, Path] = {}
    missing: list[str] = []
    for name in SOURCE_FILES:
        path = folder / name
        if path.is_file():
            paths[name] = path
        else:
            missing.append(name)
    if missing:
        raise FileNotFoundError(
            f"Missing CSV(s) in {folder}: {', '.join(missing)}"
        )
    return paths


def ingest_snapshot(
    snapshot_date: str,
    settings: Settings | None = None,
    client: storage.Client | None = None,
) -> list[UploadResult]:
    """
    Upload all MaStR CSVs for a snapshot_date folder to GCS Bronze.

    Preserves original file bytes. Callable from CLI and Airflow.
    """
    cfg = settings or get_settings()
    checksums = expected_checksums(snapshot_date)
    files = list_snapshot_files(cfg.raw_dir, snapshot_date)

    results: list[UploadResult] = []
    for source_file, path in files.items():
        result = upload_csv(
            local_path=path,
            snapshot_date=snapshot_date,
            source_file=source_file,
            bucket_name=cfg.bucket,
            project_id=cfg.project_id,
            expected_sha256=checksums[source_file],
            client=client,
        )
        results.append(result)
    return results
