"""Unit tests for checksum helpers (no GCS dependency)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mastr_data_pipeline.checksums import (
    EXPECTED_SHA256,
    SOURCE_FILES,
    expected_checksums,
    md5_file_b64,
    sha256_file,
    verify_local_checksum,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "data" / "raw" / "2026-11-09"


def test_source_files_match_expected_map_keys():
    assert set(SOURCE_FILES) == set(EXPECTED_SHA256["2026-11-09"])


def test_expected_checksums_known_snapshot():
    mapping = expected_checksums("2026-11-09")
    assert mapping["wind.csv"].startswith("a1987b46")


def test_expected_checksums_unknown_snapshot():
    with pytest.raises(ValueError, match="No expected SHA-256 map"):
        expected_checksums("1999-01-01")


def test_sha256_and_verify_against_local_snapshot_files():
    if not SNAPSHOT.is_dir():
        pytest.skip("local snapshot folder data/raw/2026-11-09 not present")

    expected = expected_checksums("2026-11-09")
    for name in SOURCE_FILES:
        path = SNAPSHOT / name
        assert path.is_file()
        digest = sha256_file(path)
        assert digest == expected[name]
        assert verify_local_checksum(path, expected[name]) == digest


def test_verify_local_checksum_mismatch(tmp_path: Path):
    path = tmp_path / "wind.csv"
    path.write_bytes(b"not-the-real-file")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_local_checksum(path, "0" * 64)


def test_md5_file_b64_matches_stdlib(tmp_path: Path):
    path = tmp_path / "sample.csv"
    payload = b"col1;col2\n1;2\n"
    path.write_bytes(payload)
    import base64

    expected = base64.b64encode(hashlib.md5(payload).digest()).decode("ascii")
    assert md5_file_b64(path) == expected
