"""Unit tests for GCS Bronze pathing and upload guards (mocked client)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mastr_data_pipeline.checksums import sha256_file
from mastr_data_pipeline.gcs_bronze import object_path, upload_csv


def test_object_path_format():
    assert (
        object_path("2026-11-09", "wind.csv")
        == "bronze/mastr/snapshot_date=2026-11-09/wind.csv"
    )


def test_upload_csv_create_only_and_integrity(tmp_path: Path):
    local = tmp_path / "wind.csv"
    payload = b"a;b\n1;2\n"
    local.write_bytes(payload)
    expected_sha = sha256_file(local)

    blob = MagicMock()
    blob.exists.return_value = False
    blob.md5_hash = __import__("base64").b64encode(
        __import__("hashlib").md5(payload).digest()
    ).decode("ascii")
    blob.metadata = {
        "sha256": expected_sha,
        "snapshot_date": "2026-11-09",
        "source_file": "wind.csv",
    }

    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket

    result = upload_csv(
        local_path=local,
        snapshot_date="2026-11-09",
        source_file="wind.csv",
        bucket_name="test-bucket",
        project_id="test-project",
        expected_sha256=expected_sha,
        client=client,
    )

    assert result.status == "uploaded"
    assert result.gs_uri == (
        "gs://test-bucket/bronze/mastr/snapshot_date=2026-11-09/wind.csv"
    )
    blob.upload_from_filename.assert_called_once()
    kwargs = blob.upload_from_filename.call_args.kwargs
    assert kwargs["if_generation_match"] == 0
    assert kwargs["content_type"] == "text/csv"


def test_upload_csv_skips_identical_existing(tmp_path: Path):
    local = tmp_path / "solar.csv"
    local.write_bytes(b"x;y\n")
    expected_sha = sha256_file(local)

    blob = MagicMock()
    blob.exists.return_value = True
    blob.metadata = {"sha256": expected_sha}

    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket

    result = upload_csv(
        local_path=local,
        snapshot_date="2026-11-09",
        source_file="solar.csv",
        bucket_name="test-bucket",
        project_id="test-project",
        expected_sha256=expected_sha,
        client=client,
    )

    assert result.status == "skipped_identical"
    blob.upload_from_filename.assert_not_called()


def test_upload_csv_refuses_overwrite_different_checksum(tmp_path: Path):
    local = tmp_path / "biomass.csv"
    local.write_bytes(b"bio\n")
    expected_sha = sha256_file(local)

    blob = MagicMock()
    blob.exists.return_value = True
    blob.metadata = {"sha256": "different" + "0" * 55}

    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        upload_csv(
            local_path=local,
            snapshot_date="2026-11-09",
            source_file="biomass.csv",
            bucket_name="test-bucket",
            project_id="test-project",
            expected_sha256=expected_sha,
            client=client,
        )


def test_upload_csv_rejects_sha_mismatch(tmp_path: Path):
    local = tmp_path / "battery.csv"
    local.write_bytes(b"batt\n")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        upload_csv(
            local_path=local,
            snapshot_date="2026-11-09",
            source_file="battery.csv",
            bucket_name="test-bucket",
            project_id="test-project",
            expected_sha256="0" * 64,
            client=MagicMock(),
        )
