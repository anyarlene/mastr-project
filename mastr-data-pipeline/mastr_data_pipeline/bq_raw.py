"""Load GCS Bronze MaStR CSVs into split BigQuery Raw tables (validate-then-replace)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from google.cloud import bigquery

from mastr_data_pipeline.checksums import SOURCE_FILES
from mastr_data_pipeline.config_loader import RAW_TABLE_BY_SOURCE, RAW_TABLES
from mastr_data_pipeline.gcs_bronze import object_path
from mastr_data_pipeline.raw_schema import (
    UNIT_ID_FIELD,
    expected_row_counts,
    payload_field_names,
    payload_schema_fields,
    raw_table_schema_fields,
)

@dataclass(frozen=True)
class RawLoadResult:
    snapshot_date: str
    staging_table: str
    destination_table: str
    row_counts: dict[str, int]
    ingested_at: str
    status: str  # replaced
    destination_tables: tuple[str, ...] = ()
    staging_tables: tuple[str, ...] = ()


def get_bq_client(project_id: str, location: str) -> bigquery.Client:
    return bigquery.Client(project=project_id, location=location)


def gcs_uri(bucket: str, snapshot_date: str, source_file: str) -> str:
    return f"gs://{bucket}/{object_path(snapshot_date, source_file)}"


def staging_table_id(snapshot_date: str, table: str) -> str:
    suffix = snapshot_date.replace("-", "")
    return f"{table}__staging_{suffix}"


def raw_table_for_source(source_file: str) -> str:
    try:
        return RAW_TABLE_BY_SOURCE[source_file]
    except KeyError as exc:
        raise ValueError(f"No Raw table mapping for source_file={source_file!r}") from exc


def fq_table(project_id: str, dataset: str, table: str) -> str:
    return f"{project_id}.{dataset}.{table}"


def ensure_dataset(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    location: str,
) -> None:
    ds = bigquery.Dataset(f"{project_id}.{dataset}")
    ds.location = location
    client.create_dataset(ds, exists_ok=True)


def ensure_raw_table(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    table: str,
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


def ensure_split_raw_tables(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
) -> None:
    """Ensure the four source-specific Raw tables exist (does not touch legacy unified)."""
    for table in RAW_TABLES:
        ensure_raw_table(client, project_id, dataset, table=table)


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


def build_source_staging_table(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    bucket: str,
    snapshot_date: str,
    source_file: str,
    ingested_at: datetime,
    staging_table: str,
) -> int:
    """Load one Bronze CSV into a per-source staging table with lineage."""
    staging_fq = fq_table(project_id, dataset, staging_table)
    schema = [
        bigquery.SchemaField(f["name"], f["type"], mode=f["mode"])
        for f in raw_table_schema_fields()
    ]
    client.delete_table(staging_fq, not_found_ok=True)
    client.create_table(bigquery.Table(staging_fq, schema=schema))

    payload_cols = ", ".join(payload_field_names())
    snap = date.fromisoformat(snapshot_date)
    ingested_at_utc = ingested_at.astimezone(timezone.utc)
    temp_table = fq_table(
        project_id,
        dataset,
        f"{staging_table}__tmp",
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
            bigquery.ScalarQueryParameter("ingested_at", "TIMESTAMP", ingested_at_utc),
        ]
    )
    client.query(insert_sql, job_config=job_config).result()
    tmp_rows = client.get_table(temp_table).num_rows or 0
    client.delete_table(temp_table, not_found_ok=True)
    return int(tmp_rows)


def build_staging_table(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    bucket: str,
    snapshot_date: str,
    ingested_at: datetime,
    staging_tables: dict[str, str] | None = None,
    staging_table: str | None = None,
) -> dict[str, int]:
    """
    Load all four Bronze CSVs into per-source staging tables.

    ``staging_tables`` maps source_file -> staging table name.
    Legacy ``staging_table`` is accepted only if staging_tables is omitted
    (builds names from RAW_TABLE_BY_SOURCE).
    """
    if staging_tables is None:
        staging_tables = {
            source_file: staging_table_id(
                snapshot_date, table=raw_table_for_source(source_file)
            )
            for source_file in SOURCE_FILES
        }
        if staging_table is not None:
            # Backward-compatible single name ignored for split loads.
            pass

    counts: dict[str, int] = {}
    for source_file in SOURCE_FILES:
        counts[source_file] = build_source_staging_table(
            client,
            project_id=project_id,
            dataset=dataset,
            bucket=bucket,
            snapshot_date=snapshot_date,
            source_file=source_file,
            ingested_at=ingested_at,
            staging_table=staging_tables[source_file],
        )
    return counts


def validate_staging(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    snapshot_date: str,
    staging_tables: dict[str, str],
) -> dict[str, Any]:
    """
    Validate per-source staging tables before touching production Raw.

    Checks:
      - each source file present with expected row count
      - installation IDs non-null / non-empty per table
      - no duplicate installation IDs within or across the four stagings
    """
    expected = expected_row_counts(snapshot_date)
    actual_counts: dict[str, int] = {}
    total_rows = 0
    null_or_blank = 0
    union_parts: list[str] = []

    for source_file in SOURCE_FILES:
        staging_fq = fq_table(project_id, dataset, staging_tables[source_file])
        count_sql = f"""
        SELECT
          COUNT(*) AS row_count,
          COUNTIF({UNIT_ID_FIELD} IS NULL OR TRIM({UNIT_ID_FIELD}) = '') AS null_or_blank_unit_ids
        FROM `{staging_fq}`
        """
        row = list(client.query(count_sql).result())[0]
        actual = int(row["row_count"])
        actual_counts[source_file] = actual
        total_rows += actual
        null_or_blank += int(row["null_or_blank_unit_ids"])
        union_parts.append(
            f"SELECT {UNIT_ID_FIELD} AS unit_id FROM `{staging_fq}`"
        )

    missing_files = [f for f in SOURCE_FILES if f not in actual_counts]
    if missing_files:
        raise ValueError(f"Staging missing source_file(s): {missing_files}")

    count_mismatches = {
        f: {"expected": expected[f], "actual": actual_counts.get(f, 0)}
        for f in SOURCE_FILES
        if actual_counts.get(f, 0) != expected[f]
    }
    if count_mismatches:
        raise ValueError(
            f"Row count mismatch for snapshot {snapshot_date}: {count_mismatches}"
        )

    if null_or_blank:
        raise ValueError(
            f"Staging has {null_or_blank} null/blank installation IDs ({UNIT_ID_FIELD})"
        )

    distinct_sql = f"""
    SELECT COUNT(DISTINCT unit_id) AS distinct_unit_ids
    FROM (
      {' UNION ALL '.join(union_parts)}
    )
    """
    distinct_ids = int(list(client.query(distinct_sql).result())[0]["distinct_unit_ids"])
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
    Atomically replace one snapshot_date in one production Raw table from staging.

    Does not modify other Raw tables (including legacy raw_mastr_units).
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


def replace_all_snapshots_atomically(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset: str,
    staging_tables: dict[str, str],
    snapshot_date: str,
) -> None:
    """Replace snapshot_date in all four split Raw tables from validated stagings."""
    for source_file in SOURCE_FILES:
        replace_snapshot_atomically(
            client,
            project_id=project_id,
            dataset=dataset,
            table=raw_table_for_source(source_file),
            staging_table=staging_tables[source_file],
            snapshot_date=snapshot_date,
        )


def load_snapshot_to_raw(
    *,
    project_id: str,
    bucket: str,
    snapshot_date: str,
    dataset: str,
    location: str,
    client: bigquery.Client | None = None,
    ingested_at: datetime | None = None,
    keep_staging: bool = False,
) -> RawLoadResult:
    """
    Validate-then-replace loader for one snapshot_date into four Raw tables.

    ``dataset`` and ``location`` are required (typically Settings.bq_dataset /
    Settings.bq_location from env vars BQ_DATASET / BQ_LOCATION).

    1) Ensure dataset and split Raw tables exist (legacy backup table untouched)
    2) Build per-source staging from GCS Bronze
    3) Validate counts, IDs, duplicates across stagings
    4) Atomically replace each production table for that snapshot only
    """
    bq = client or get_bq_client(project_id, location=location)
    ingested = ingested_at or datetime.now(timezone.utc)
    staging_tables = {
        source_file: staging_table_id(
            snapshot_date, table=raw_table_for_source(source_file)
        )
        for source_file in SOURCE_FILES
    }
    staging_label = ",".join(staging_tables[f] for f in SOURCE_FILES)
    destination_tables = tuple(
        fq_table(project_id, dataset, raw_table_for_source(f)) for f in SOURCE_FILES
    )

    ensure_dataset(bq, project_id, dataset, location=location)
    ensure_split_raw_tables(bq, project_id, dataset)

    try:
        row_counts = build_staging_table(
            bq,
            project_id=project_id,
            dataset=dataset,
            bucket=bucket,
            snapshot_date=snapshot_date,
            ingested_at=ingested,
            staging_tables=staging_tables,
        )
        validate_staging(
            bq,
            project_id=project_id,
            dataset=dataset,
            snapshot_date=snapshot_date,
            staging_tables=staging_tables,
        )
        replace_all_snapshots_atomically(
            bq,
            project_id=project_id,
            dataset=dataset,
            staging_tables=staging_tables,
            snapshot_date=snapshot_date,
        )
    except Exception:
        raise
    else:
        if not keep_staging:
            for staging in staging_tables.values():
                bq.delete_table(fq_table(project_id, dataset, staging), not_found_ok=True)

    return RawLoadResult(
        snapshot_date=snapshot_date,
        staging_table=staging_label,
        destination_table=f"{project_id}.{dataset}.{{{','.join(RAW_TABLES)}}}",
        row_counts=row_counts,
        ingested_at=ingested.astimezone(timezone.utc).isoformat(),
        status="replaced",
        destination_tables=destination_tables,
        staging_tables=tuple(staging_tables[f] for f in SOURCE_FILES),
    )
