"""SHA-256 helpers and expected checksums for known MaStR snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path

from mastr_data_pipeline.config_loader import SOURCE_FILES, load_snapshots

# Re-export for callers that import SOURCE_FILES from checksums.
__all__ = [
    "EXPECTED_SHA256",
    "SOURCE_FILES",
    "expected_checksums",
    "md5_file_b64",
    "sha256_file",
    "verify_local_checksum",
]

# snapshot_date is the dated folder label under data/raw/, not necessarily
# the official MaStR export timestamp.
EXPECTED_SHA256: dict[str, dict[str, str]] = {
    snapshot_date: dict(entry["sha256"])
    for snapshot_date, entry in load_snapshots().items()
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the hex SHA-256 of a file without modifying it."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def md5_file_b64(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the base64 MD5 digest (GCS blob.md5_hash format)."""
    import base64

    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def expected_checksums(snapshot_date: str) -> dict[str, str]:
    """Return expected SHA-256 map for a snapshot_date folder label."""
    try:
        return dict(EXPECTED_SHA256[snapshot_date])
    except KeyError as exc:
        known = ", ".join(sorted(EXPECTED_SHA256)) or "(none)"
        raise ValueError(
            f"No expected SHA-256 map for snapshot_date={snapshot_date!r}. "
            f"Known snapshots: {known}"
        ) from exc


def verify_local_checksum(path: Path, expected_sha256: str) -> str:
    """Compute SHA-256 and raise if it does not match the expected value."""
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path.name}: "
            f"expected {expected_sha256}, got {actual}"
        )
    return actual
