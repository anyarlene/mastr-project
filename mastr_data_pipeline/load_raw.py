"""Orchestrate GCS Bronze → BigQuery Raw for a snapshot_date."""

from __future__ import annotations

from datetime import datetime

from google.cloud import bigquery

from mastr_data_pipeline.bq_raw import RawLoadResult, load_snapshot_to_raw
from mastr_data_pipeline.config import Settings, get_settings


def load_raw_snapshot(
    snapshot_date: str,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    ingested_at: datetime | None = None,
    keep_staging: bool = False,
) -> RawLoadResult:
    """
    Load one MaStR snapshot from GCS Bronze into the four split Raw tables.

    Writes: raw_mastr_wind / raw_mastr_solar / raw_mastr_biomass / raw_mastr_storage.
    Does not modify legacy mastr_raw.raw_mastr_units.

    Callable from CLI and Airflow. Idempotent via validate-then-atomic-replace.
    """
    cfg = settings or get_settings()
    return load_snapshot_to_raw(
        project_id=cfg.project_id,
        bucket=cfg.bucket,
        snapshot_date=snapshot_date,
        dataset=cfg.bq_dataset,
        location=cfg.bq_location,
        client=client,
        ingested_at=ingested_at,
        keep_staging=keep_staging,
    )
