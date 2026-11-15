"""Environment-based settings for MaStR Bronze ingestion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    project_id: str
    bucket: str
    raw_dir: Path


def get_settings() -> Settings:
    """
    Load settings from environment variables.

    Required:
      - GCP_PROJECT_ID
      - GCS_BUCKET

    Optional:
      - MASTR_RAW_DIR (default: <repo>/data/raw)
      - GOOGLE_APPLICATION_CREDENTIALS (used by google-cloud-storage ADC)
    """
    project_id = os.environ.get("GCP_PROJECT_ID", "").strip()
    bucket = os.environ.get("GCS_BUCKET", "").strip()

    missing = [
        name
        for name, value in (
            ("GCP_PROJECT_ID", project_id),
            ("GCS_BUCKET", bucket),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )

    raw_dir_value = os.environ.get("MASTR_RAW_DIR", "").strip()
    raw_dir = Path(raw_dir_value) if raw_dir_value else REPO_ROOT / "data" / "raw"

    return Settings(project_id=project_id, bucket=bucket, raw_dir=raw_dir)
