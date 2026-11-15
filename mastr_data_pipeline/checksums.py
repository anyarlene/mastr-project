"""SHA-256 helpers and expected checksums for known MaStR snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path

# snapshot_date is the dated folder label under data/raw/, not necessarily
# the official MaStR export timestamp.
EXPECTED_SHA256: dict[str, dict[str, str]] = {
    "2026-11-09": {
        "wind.csv": (
            "a1987b4647c6227138a4062f1c123c05d367a803ff634fb6ca69357d3bc0a192"
        ),
        "solar.csv": (
            "3b26e599bfa7f464c046b010ae51c99937eca58c96b3ed9593c0e6dc0b769a96"
        ),
        "biomass.csv": (
            "2c52fcc0c9b1e317f2047f86627f7a8859bc5fc56df152da30a99d8238fcbb70"
        ),
        "battery.csv": (
            "fa1fdf099c05c4fee23a49d14054975225dfe1303660fb339756f5f9ff9803c2"
        ),
    }
}

SOURCE_FILES: tuple[str, ...] = (
    "wind.csv",
    "solar.csv",
    "biomass.csv",
    "battery.csv",
)


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
        return EXPECTED_SHA256[snapshot_date]
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
