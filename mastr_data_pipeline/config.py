"""Environment-based settings for MaStR Bronze and BigQuery Raw."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BQ_DATASET = "mastr_raw"
DEFAULT_BQ_TABLE = "raw_mastr_units"
DEFAULT_BQ_LOCATION = "europe-west3"


@dataclass(frozen=True)
class Settings:
    project_id: str
    bucket: str
    raw_dir: Path
    bq_dataset: str = DEFAULT_BQ_DATASET
    bq_table: str = DEFAULT_BQ_TABLE
    bq_location: str = DEFAULT_BQ_LOCATION


def get_settings() -> Settings:
    """
    Load settings from environment variables.

    Required:
      - GCP_PROJECT_ID
      - GCS_BUCKET

    Optional:
      - MASTR_RAW_DIR (default: <repo>/data/raw)
      - BQ_DATASET (default: mastr_raw)
      - BQ_TABLE (default: raw_mastr_units)
      - BQ_LOCATION (default: europe-west3)
      - GOOGLE_APPLICATION_CREDENTIALS (ADC / service-account key path)
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

    return Settings(
        project_id=project_id,
        bucket=bucket,
        raw_dir=raw_dir,
        bq_dataset=os.environ.get("BQ_DATASET", DEFAULT_BQ_DATASET).strip()
        or DEFAULT_BQ_DATASET,
        bq_table=os.environ.get("BQ_TABLE", DEFAULT_BQ_TABLE).strip()
        or DEFAULT_BQ_TABLE,
        bq_location=os.environ.get("BQ_LOCATION", DEFAULT_BQ_LOCATION).strip()
        or DEFAULT_BQ_LOCATION,
    )
