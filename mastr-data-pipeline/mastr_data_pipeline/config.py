"""Environment-based settings for MaStR Bronze and BigQuery Raw."""

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
    bq_dataset: str
    bq_location: str


def get_settings() -> Settings:
    """
    Load settings from environment variables.

    Required:
      - GCP_PROJECT_ID
      - GCS_BUCKET
      - MASTR_RAW_DIR
      - BQ_DATASET
      - BQ_LOCATION

    Optional:
      - GOOGLE_APPLICATION_CREDENTIALS (ADC / service-account key path)
    """
    project_id = os.environ.get("GCP_PROJECT_ID", "").strip()
    bucket = os.environ.get("GCS_BUCKET", "").strip()
    raw_dir_value = os.environ.get("MASTR_RAW_DIR", "").strip()
    bq_dataset = os.environ.get("BQ_DATASET", "").strip()
    bq_location = os.environ.get("BQ_LOCATION", "").strip()

    missing = [
        name
        for name, value in (
            ("GCP_PROJECT_ID", project_id),
            ("GCS_BUCKET", bucket),
            ("MASTR_RAW_DIR", raw_dir_value),
            ("BQ_DATASET", bq_dataset),
            ("BQ_LOCATION", bq_location),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )

    return Settings(
        project_id=project_id,
        bucket=bucket,
        raw_dir=Path(raw_dir_value),
        bq_dataset=bq_dataset,
        bq_location=bq_location,
    )
