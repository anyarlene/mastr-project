"""Upload original MaStR CSV bytes to GCS Bronze (create-only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google.cloud import storage

from mastr_data_pipeline.checksums import md5_file_b64, sha256_file


@dataclass(frozen=True)
class UploadResult:
    source_file: str
    snapshot_date: str
    local_path: str
    gs_uri: str
    sha256: str
    status: str  # uploaded | skipped_identical


def object_path(snapshot_date: str, source_file: str) -> str:
    """
    Build the Bronze object key.

    Example:
      bronze/mastr/snapshot_date=2026-11-09/wind.csv
    """
    return f"bronze/mastr/snapshot_date={snapshot_date}/{source_file}"


def get_storage_client(project_id: str) -> storage.Client:
    """Build a Storage client (ADC / GOOGLE_APPLICATION_CREDENTIALS)."""
    return storage.Client(project=project_id)


def upload_csv(
    *,
    local_path: Path,
    snapshot_date: str,
    source_file: str,
    bucket_name: str,
    project_id: str,
    expected_sha256: str,
    client: storage.Client | None = None,
) -> UploadResult:
    """
    Upload one CSV unchanged to GCS Bronze.

    - Verifies local SHA-256 against the expected value.
    - Skips if the object already exists with the same SHA-256 metadata.
    - Refuses to overwrite if the object exists with a different checksum.
    - Uses create-only upload (if_generation_match=0).
    - Verifies GCS transfer integrity via MD5 after upload.
    """
    if local_path.name != source_file:
        raise ValueError(
            f"source_file {source_file!r} does not match path name {local_path.name!r}"
        )
    if not local_path.is_file():
        raise FileNotFoundError(f"Local CSV not found: {local_path}")

    actual_sha256 = sha256_file(local_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {source_file}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    storage_client = client or get_storage_client(project_id)
    bucket = storage_client.bucket(bucket_name)
    blob_name = object_path(snapshot_date, source_file)
    blob = bucket.blob(blob_name)
    gs_uri = f"gs://{bucket_name}/{blob_name}"

    if blob.exists(storage_client):
        blob.reload()
        remote_sha = (blob.metadata or {}).get("sha256")
        if remote_sha == actual_sha256:
            return UploadResult(
                source_file=source_file,
                snapshot_date=snapshot_date,
                local_path=str(local_path),
                gs_uri=gs_uri,
                sha256=actual_sha256,
                status="skipped_identical",
            )
        raise FileExistsError(
            f"Refusing to overwrite {gs_uri}: object exists with different "
            f"sha256 (remote={remote_sha!r}, local={actual_sha256!r})"
        )

    local_md5 = md5_file_b64(local_path)
    blob.metadata = {
        "sha256": actual_sha256,
        "snapshot_date": snapshot_date,
        "source_file": source_file,
    }
    # Create-only: fail if another writer created the object first.
    blob.upload_from_filename(
        str(local_path),
        content_type="text/csv",
        if_generation_match=0,
    )

    blob.reload()
    remote_md5 = blob.md5_hash
    if remote_md5 != local_md5:
        raise RuntimeError(
            f"GCS transfer integrity failure for {gs_uri}: "
            f"local_md5={local_md5!r}, remote_md5={remote_md5!r}"
        )
    remote_sha = (blob.metadata or {}).get("sha256")
    if remote_sha != actual_sha256:
        raise RuntimeError(
            f"GCS metadata sha256 mismatch for {gs_uri}: "
            f"expected {actual_sha256}, got {remote_sha!r}"
        )

    return UploadResult(
        source_file=source_file,
        snapshot_date=snapshot_date,
        local_path=str(local_path),
        gs_uri=gs_uri,
        sha256=actual_sha256,
        status="uploaded",
    )
