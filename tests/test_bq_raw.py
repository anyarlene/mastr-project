"""Mocked unit tests for BigQuery Raw validate-then-replace loader."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mastr_data_pipeline.bq_raw import (
    build_staging_table,
    gcs_uri,
    load_snapshot_to_raw,
    replace_snapshot_atomically,
    staging_table_id,
    validate_staging,
)
from mastr_data_pipeline.checksums import SOURCE_FILES


def test_gcs_uri_and_staging_table_id():
    assert (
        gcs_uri("your-bronze-bucket-name", "2026-11-09", "wind.csv")
        == "gs://your-bronze-bucket-name/bronze/mastr/snapshot_date=2026-11-09/wind.csv"
    )
    assert staging_table_id("2026-11-09") == "raw_mastr_units__staging_20261109"


def test_validate_staging_ok():
    client = MagicMock()

    class Row(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)

    count_rows = [
        Row({"source_file": "wind.csv", "row_count": 278}),
        Row({"source_file": "solar.csv", "row_count": 20861}),
        Row({"source_file": "biomass.csv", "row_count": 56}),
        Row({"source_file": "battery.csv", "row_count": 11416}),
    ]
    quality_rows = [
        Row(
            {
                "total_rows": 32611,
                "null_or_blank_unit_ids": 0,
                "distinct_unit_ids": 32611,
            }
        )
    ]

    def query_side_effect(sql, job_config=None):
        job = MagicMock()
        if "GROUP BY source_file" in sql:
            job.result.return_value = count_rows
        else:
            job.result.return_value = quality_rows
        return job

    client.query.side_effect = query_side_effect

    result = validate_staging(
        client,
        project_id="proj",
        dataset="mastr_raw",
        staging_table="raw_mastr_units__staging_20261109",
        snapshot_date="2026-11-09",
    )
    assert result["total_rows"] == 32611
    assert result["row_counts"]["solar.csv"] == 20861


def test_validate_staging_row_count_mismatch():
    client = MagicMock()
    count_rows = [
        {"source_file": "wind.csv", "row_count": 277},
        {"source_file": "solar.csv", "row_count": 20861},
        {"source_file": "biomass.csv", "row_count": 56},
        {"source_file": "battery.csv", "row_count": 11416},
    ]
    job = MagicMock()
    job.result.return_value = count_rows
    client.query.return_value = job

    with pytest.raises(ValueError, match="Row count mismatch"):
        validate_staging(
            client,
            project_id="proj",
            dataset="mastr_raw",
            staging_table="stg",
            snapshot_date="2026-11-09",
        )


def test_validate_staging_duplicate_unit_ids():
    client = MagicMock()

    def query_side_effect(sql, job_config=None):
        job = MagicMock()
        if "GROUP BY source_file" in sql:
            job.result.return_value = [
                {"source_file": f, "row_count": c}
                for f, c in (
                    ("wind.csv", 278),
                    ("solar.csv", 20861),
                    ("biomass.csv", 56),
                    ("battery.csv", 11416),
                )
            ]
        else:
            job.result.return_value = [
                {
                    "total_rows": 32611,
                    "null_or_blank_unit_ids": 0,
                    "distinct_unit_ids": 32610,
                }
            ]
        return job

    client.query.side_effect = query_side_effect

    with pytest.raises(ValueError, match="Duplicate installation IDs"):
        validate_staging(
            client,
            project_id="proj",
            dataset="mastr_raw",
            staging_table="stg",
            snapshot_date="2026-11-09",
        )


def test_replace_snapshot_atomically_runs_transaction_script():
    client = MagicMock()
    job = MagicMock()
    client.query.return_value = job

    replace_snapshot_atomically(
        client,
        project_id="proj",
        dataset="mastr_raw",
        table="raw_mastr_units",
        staging_table="raw_mastr_units__staging_20261109",
        snapshot_date="2026-11-09",
    )

    sql = client.query.call_args.args[0]
    assert "BEGIN TRANSACTION" in sql
    assert "DELETE FROM" in sql
    assert "INSERT INTO" in sql
    assert "COMMIT TRANSACTION" in sql
    job.result.assert_called_once()


def test_load_snapshot_to_raw_validate_then_replace_order():
    client = MagicMock()
    calls: list[str] = []

    with patch(
        "mastr_data_pipeline.bq_raw.ensure_dataset",
        side_effect=lambda *a, **k: calls.append("ensure_dataset"),
    ), patch(
        "mastr_data_pipeline.bq_raw.ensure_raw_table",
        side_effect=lambda *a, **k: calls.append("ensure_raw_table"),
    ), patch(
        "mastr_data_pipeline.bq_raw.build_staging_table",
        side_effect=lambda *a, **k: (
            calls.append("build_staging"),
            {f: 1 for f in SOURCE_FILES},
        )[1],
    ), patch(
        "mastr_data_pipeline.bq_raw.validate_staging",
        side_effect=lambda *a, **k: (
            calls.append("validate"),
            {"row_counts": {}, "total_rows": 4, "distinct_unit_ids": 4},
        )[1],
    ), patch(
        "mastr_data_pipeline.bq_raw.replace_snapshot_atomically",
        side_effect=lambda *a, **k: calls.append("replace"),
    ):
        result = load_snapshot_to_raw(
            project_id="proj",
            bucket="bucket",
            snapshot_date="2026-11-09",
            client=client,
            ingested_at=datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc),
            keep_staging=True,
        )

    assert calls == [
        "ensure_dataset",
        "ensure_raw_table",
        "build_staging",
        "validate",
        "replace",
    ]
    assert result.status == "replaced"
    assert result.destination_table == "proj.mastr_raw.raw_mastr_units"


def test_load_snapshot_to_raw_skips_replace_when_validation_fails():
    client = MagicMock()

    with patch("mastr_data_pipeline.bq_raw.ensure_dataset"), patch(
        "mastr_data_pipeline.bq_raw.ensure_raw_table"
    ), patch(
        "mastr_data_pipeline.bq_raw.build_staging_table",
        return_value={f: 1 for f in SOURCE_FILES},
    ), patch(
        "mastr_data_pipeline.bq_raw.validate_staging",
        side_effect=ValueError("Row count mismatch"),
    ), patch(
        "mastr_data_pipeline.bq_raw.replace_snapshot_atomically"
    ) as replace:
        with pytest.raises(ValueError, match="Row count mismatch"):
            load_snapshot_to_raw(
                project_id="proj",
                bucket="bucket",
                snapshot_date="2026-11-09",
                client=client,
            )
        replace.assert_not_called()


def test_build_staging_table_loads_each_source_file():
    client = MagicMock()
    client.get_table.return_value.num_rows = 10

    with patch("mastr_data_pipeline.bq_raw._load_csv_to_temp") as load_tmp:
        counts = build_staging_table(
            client,
            project_id="proj",
            dataset="mastr_raw",
            bucket="bucket",
            snapshot_date="2026-11-09",
            ingested_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
            staging_table="stg",
        )

    assert load_tmp.call_count == 4
    assert set(counts) == set(SOURCE_FILES)
    assert client.query.call_count == 4
