"""Load GCS Bronze MaStR CSVs into BigQuery Raw with validate-then-replace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from google.cloud import bigquery

from mastr_data_pipeline.checksums import SOURCE_FILES
from mastr_data_pipeline.gcs_bronze import object_path
from mastr_data_pipeline.raw_schema import (
    UNIT_ID_FIELD,
    expected_row_counts,
    payload_field_names,
    payload_schema_fields,
    raw_table_schema_fields,
)

DEFAULT_DATASET = "mastr_raw"
DEFAULT_TABLE = "raw_mastr_units"
DEFAULT_LOCATION = "europe-west3"


@dataclass(frozen=True)
class RawLoadResult:
    snapshot_date: str
    staging_table: str
    destination_table: str
    row_counts: dict[str, int]
    ingested_at: str
    status: str  # replaced


def get_bq_client(project_id: str, location: str = DEFAULT_LOCATION) -> bigquery.Client:
    return bigquery.Client(project=project_id, location=location)


def gcs_uri(bucket: str, snapshot_date: str, source_file: str) -> str:
    return f"gs://{bucket}/{object_path(snapshot_date, source_file)}"


def staging_table_id(snapshot_date: str, table: str = DEFAULT_TABLE) -> str:
    suffix = snapshot_date.replace("-", "")
    return f"{table}__staging_{suffix}"


def fq_table(project_id: str, dataset: str, table: str) -> str:
    return f"{project_id}.{dataset}.{table}"


def ensure_dataset(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    location: str = DEFAULT_LOCATION,
) -> None:
    ds = bigquery.Dataset(f"{project_id}.{dataset}")
    ds.location = location
    client.create_dataset(ds, exists_ok=True)


def ensure_raw_table(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    table: str = DEFAULT_TABLE,
) -> None:
    table_ref = fq_table(project_id, dataset, table)
    schema = [
        bigquery.SchemaField(f["name"], f["type"], mode=f["mode"])
        for f in raw_table_schema_fields()
    ]
    bq_table = bigquery.Table(table_ref, schema=schema)
    bq_table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="snapshot_date",
    )
    client.create_table(bq_table, exists_ok=True)


def _load_csv_to_temp(
    client: bigquery.Client,
    *,
    uri: str,
    temp_table: str,
) -> None:
    """Load one CSV into a temp table (64 STRING columns, header skipped)."""
    schema = [
        bigquery.SchemaField(f["name"], f["type"], mode=f.get("mode", "NULLABLE"))
        for f in payload_schema_fields()
    ]
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.CSV,
        field_delimiter=";",
        skip_leading_rows=1,
        quote_character='"',
        encoding="UTF-8",
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
        allow_jagged_rows=False,
    )
    job = client.load_table_from_uri(uri, temp_table, job_config=job_config)
    job.result()


def build_staging_table(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    bucket: str,
    snapshot_date: str,
    ingested_at: datetime,
    staging_table: str,
) -> dict[str, int]:
    """
    Load all four Bronze CSVs into a staging table with lineage columns.

    Does not modify the production Raw table.
    """
    staging_fq = fq_table(project_id, dataset, staging_table)
    schema = [
        bigquery.SchemaField(f["name"], f["type"], mode=f["mode"])
        for f in raw_table_schema_fields()
    ]
    # Recreate empty staging table for this run.
    client.delete_table(staging_fq, not_found_ok=True)
    client.create_table(bigquery.Table(staging_fq, schema=schema))

    payload_cols = ", ".join(payload_field_names())
    counts: dict[str, int] = {}
    snap = date.fromisoformat(snapshot_date)
    ingested_at_utc = ingested_at.astimezone(timezone.utc)

    for source_file in SOURCE_FILES:
        temp_table = fq_table(
            project_id,
            dataset,
            f"{staging_table}__tmp_{source_file.replace('.', '_')}",
        )
        uri = gcs_uri(bucket, snapshot_date, source_file)
        _load_csv_to_temp(client, uri=uri, temp_table=temp_table)

        insert_sql = f"""
        INSERT INTO `{staging_fq}` ({payload_cols}, source_file, snapshot_date, ingested_at)
        SELECT
          {payload_cols},
          @source_file AS source_file,
          @snapshot_date AS snapshot_date,
          @ingested_at AS ingested_at
        FROM `{temp_table}`
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source_file", "STRING", source_file),
                bigquery.ScalarQueryParameter("snapshot_date", "DATE", snap),
                bigquery.ScalarQueryParameter(
                    "ingested_at", "TIMESTAMP", ingested_at_utc
                ),
            ]
        )
        client.query(insert_sql, job_config=job_config).result()
        tmp_rows = client.get_table(temp_table).num_rows or 0
        counts[source_file] = int(tmp_rows)
        client.delete_table(temp_table, not_found_ok=True)

    return counts


def validate_staging(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    staging_table: str,
    snapshot_date: str,
) -> dict[str, Any]:
    """
    Validate staging before touching production Raw.

    Checks:
      - all four source files present
      - row counts match snapshot-specific expectations
      - installation IDs non-null / non-empty
      - no duplicate installation IDs within the snapshot
    """
    expected = expected_row_counts(snapshot_date)
    staging_fq = fq_table(project_id, dataset, staging_table)

    counts_sql = f"""
    SELECT source_file, COUNT(*) AS row_count
    FROM `{staging_fq}`
    GROUP BY source_file
    """
    counts_rows = list(client.query(counts_sql).result())
    actual_counts = {r["source_file"]: int(r["row_count"]) for r in counts_rows}

    missing_files = [f for f in SOURCE_FILES if f not in actual_counts]
    if missing_files:
        raise ValueError(f"Staging missing source_file(s): {missing_files}")

    count_mismatches = {
        f: {"expected": expected[f], "actual": actual_counts.get(f, 0)}
        for f in SOURCE_FILES
        if actual_counts.get(f, 0) != expected[f]
    }
    if count_mismatches:
        raise ValueError(f"Row count mismatch for snapshot {snapshot_date}: {count_mismatches}")

    quality_sql = f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNTIF({UNIT_ID_FIELD} IS NULL OR TRIM({UNIT_ID_FIELD}) = '') AS null_or_blank_unit_ids,
      COUNT(DISTINCT {UNIT_ID_FIELD}) AS distinct_unit_ids
    FROM `{staging_fq}`
    """
    quality = list(client.query(quality_sql).result())[0]
    total_rows = int(quality["total_rows"])
    null_or_blank = int(quality["null_or_blank_unit_ids"])
    distinct_ids = int(quality["distinct_unit_ids"])

    if null_or_blank:
        raise ValueError(
            f"Staging has {null_or_blank} null/blank installation IDs ({UNIT_ID_FIELD})"
        )
    if distinct_ids != total_rows:
        raise ValueError(
            f"Duplicate installation IDs in staging: total_rows={total_rows}, "
            f"distinct_unit_ids={distinct_ids}"
        )

    expected_total = sum(expected.values())
    if total_rows != expected_total:
        raise ValueError(
            f"Staging total rows {total_rows} != expected total {expected_total}"
        )

    return {
        "row_counts": actual_counts,
        "total_rows": total_rows,
        "distinct_unit_ids": distinct_ids,
    }


def replace_snapshot_atomically(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    table: str,
    staging_table: str,
    snapshot_date: str,
) -> None:
    """
    Atomically replace one snapshot_date in production Raw from validated staging.

    Uses a BigQuery multi-statement transaction so a failure leaves existing
    production rows for that snapshot unchanged.
    """
    raw_fq = fq_table(project_id, dataset, table)
    staging_fq = fq_table(project_id, dataset, staging_table)
    snap = date.fromisoformat(snapshot_date)

    script = f"""
    BEGIN TRANSACTION;
    DELETE FROM `{raw_fq}`
    WHERE snapshot_date = @snapshot_date;
    INSERT INTO `{raw_fq}`
    SELECT * FROM `{staging_fq}`;
    COMMIT TRANSACTION;
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("snapshot_date", "DATE", snap),
        ]
    )
    client.query(script, job_config=job_config).result()


def load_snapshot_to_raw(
    *,
    project_id: str,
    bucket: str,
    snapshot_date: str,
    dataset: str = DEFAULT_DATASET,
    table: str = DEFAULT_TABLE,
    location: str = DEFAULT_LOCATION,
    client: bigquery.Client | None = None,
    ingested_at: datetime | None = None,
    keep_staging: bool = False,
) -> RawLoadResult:
    """
    Validate-then-replace loader for one snapshot_date.

    1) Ensure dataset/table exist
    2) Build staging from GCS Bronze (four CSVs)
    3) Validate staging (counts, IDs, duplicates, completeness)
    4) Atomically replace production rows for that snapshot only
    """
    bq = client or get_bq_client(project_id, location=location)
    ingested = ingested_at or datetime.now(timezone.utc)
    staging = staging_table_id(snapshot_date, table=table)

    ensure_dataset(bq, project_id, dataset, location=location)
    ensure_raw_table(bq, project_id, dataset, table=table)

    try:
        row_counts = build_staging_table(
            bq,
            project_id=project_id,
            dataset=dataset,
            bucket=bucket,
            snapshot_date=snapshot_date,
            ingested_at=ingested,
            staging_table=staging,
        )
        validate_staging(
            bq,
            project_id=project_id,
            dataset=dataset,
            staging_table=staging,
            snapshot_date=snapshot_date,
        )
        replace_snapshot_atomically(
            bq,
            project_id=project_id,
            dataset=dataset,
            table=table,
            staging_table=staging,
            snapshot_date=snapshot_date,
        )
    except Exception:
        # Leave production untouched; keep staging for debugging unless asked otherwise.
        raise
    else:
        if not keep_staging:
            bq.delete_table(
                fq_table(project_id, dataset, staging), not_found_ok=True
            )

    return RawLoadResult(
        snapshot_date=snapshot_date,
        staging_table=staging,
        destination_table=fq_table(project_id, dataset, table),
        row_counts=row_counts,
        ingested_at=ingested.astimezone(timezone.utc).isoformat(),
        status="replaced",
    )
