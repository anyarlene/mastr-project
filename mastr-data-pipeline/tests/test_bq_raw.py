"""Mocked unit tests for BigQuery Raw validate-then-replace loader (split tables)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mastr_data_pipeline.bq_raw import (
    build_staging_table,
    gcs_uri,
    load_snapshot_to_raw,
    raw_table_for_source,
    replace_snapshot_atomically,
    staging_table_id,
    validate_staging,
)
from mastr_data_pipeline.checksums import SOURCE_FILES
from mastr_data_pipeline.config_loader import RAW_TABLE_BY_SOURCE, RAW_TABLES


def test_gcs_uri_and_staging_table_id():
    assert (
        gcs_uri("test-mastr-bronze", "2026-11-09", "wind.csv")
        == "gs://test-mastr-bronze/bronze/mastr/snapshot_date=2026-11-09/wind.csv"
    )
    assert (
        staging_table_id("2026-11-09", table="raw_mastr_wind")
        == "raw_mastr_wind__staging_20261109"
    )


def test_raw_table_mapping():
    assert raw_table_for_source("battery.csv") == "raw_mastr_storage"
    assert list(RAW_TABLES) == [
        "raw_mastr_wind",
        "raw_mastr_solar",
        "raw_mastr_biomass",
        "raw_mastr_storage",
    ]
    assert set(RAW_TABLE_BY_SOURCE) == set(SOURCE_FILES)


def _split_staging_tables() -> dict[str, str]:
    return {
        f: staging_table_id("2026-11-09", table=raw_table_for_source(f))
        for f in SOURCE_FILES
    }


def test_validate_staging_ok():
    client = MagicMock()
    expected = {
        "wind.csv": 278,
        "solar.csv": 20861,
        "biomass.csv": 56,
        "battery.csv": 11416,
    }
    call_n = {"i": 0}

    def query_side_effect(sql, job_config=None):
        job = MagicMock()
        if "COUNT(DISTINCT unit_id)" in sql:
            job.result.return_value = [{"distinct_unit_ids": 32611}]
        else:
            # one count query per source file
            source_file = SOURCE_FILES[call_n["i"] % 4]
            call_n["i"] += 1
            job.result.return_value = [
                {
                    "row_count": expected[source_file],
                    "null_or_blank_unit_ids": 0,
                }
            ]
        return job

    client.query.side_effect = query_side_effect

    result = validate_staging(
        client,
        project_id="proj",
        dataset="mastr_raw",
        snapshot_date="2026-11-09",
        staging_tables=_split_staging_tables(),
    )
    assert result["total_rows"] == 32611
    assert result["row_counts"]["solar.csv"] == 20861


def test_validate_staging_row_count_mismatch():
    client = MagicMock()

    def query_side_effect(sql, job_config=None):
        job = MagicMock()
        # First source (wind) returns wrong count
        job.result.return_value = [
            {"row_count": 277, "null_or_blank_unit_ids": 0}
        ]
        return job

    client.query.side_effect = query_side_effect

    with pytest.raises(ValueError, match="Row count mismatch"):
        validate_staging(
            client,
            project_id="proj",
            dataset="mastr_raw",
            snapshot_date="2026-11-09",
            staging_tables=_split_staging_tables(),
        )


def test_validate_staging_duplicate_unit_ids():
    client = MagicMock()
    expected = {
        "wind.csv": 278,
        "solar.csv": 20861,
        "biomass.csv": 56,
        "battery.csv": 11416,
    }
    call_n = {"i": 0}

    def query_side_effect(sql, job_config=None):
        job = MagicMock()
        if "COUNT(DISTINCT unit_id)" in sql:
            job.result.return_value = [{"distinct_unit_ids": 32610}]
        else:
            source_file = SOURCE_FILES[call_n["i"] % 4]
            call_n["i"] += 1
            job.result.return_value = [
                {
                    "row_count": expected[source_file],
                    "null_or_blank_unit_ids": 0,
                }
            ]
        return job

    client.query.side_effect = query_side_effect

    with pytest.raises(ValueError, match="Duplicate installation IDs"):
        validate_staging(
            client,
            project_id="proj",
            dataset="mastr_raw",
            snapshot_date="2026-11-09",
            staging_tables=_split_staging_tables(),
        )


def test_replace_snapshot_atomically_runs_transaction_script():
    client = MagicMock()
    job = MagicMock()
    client.query.return_value = job

    replace_snapshot_atomically(
        client,
        project_id="proj",
        dataset="mastr_raw",
        table="raw_mastr_wind",
        staging_table="raw_mastr_wind__staging_20261109",
        snapshot_date="2026-11-09",
    )

    sql = client.query.call_args.args[0]
    assert "BEGIN TRANSACTION" in sql
    assert "DELETE FROM" in sql
    assert "`proj.mastr_raw.raw_mastr_wind`" in sql
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
        "mastr_data_pipeline.bq_raw.ensure_split_raw_tables",
        side_effect=lambda *a, **k: calls.append("ensure_split_raw_tables"),
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
        "mastr_data_pipeline.bq_raw.replace_all_snapshots_atomically",
        side_effect=lambda *a, **k: calls.append("replace"),
    ):
        result = load_snapshot_to_raw(
            project_id="proj",
            bucket="bucket",
            snapshot_date="2026-11-09",
            dataset="mastr_raw",
            location="europe-west3",
            client=client,
            ingested_at=datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc),
            keep_staging=True,
        )

    assert calls == [
        "ensure_dataset",
        "ensure_split_raw_tables",
        "build_staging",
        "validate",
        "replace",
    ]
    assert result.status == "replaced"
    assert "raw_mastr_wind" in result.destination_table
    assert "raw_mastr_storage" in result.destination_table
    assert len(result.destination_tables) == 4


def test_load_snapshot_to_raw_skips_replace_when_validation_fails():
    client = MagicMock()

    with patch("mastr_data_pipeline.bq_raw.ensure_dataset"), patch(
        "mastr_data_pipeline.bq_raw.ensure_split_raw_tables"
    ), patch(
        "mastr_data_pipeline.bq_raw.build_staging_table",
        return_value={f: 1 for f in SOURCE_FILES},
    ), patch(
        "mastr_data_pipeline.bq_raw.validate_staging",
        side_effect=ValueError("Row count mismatch"),
    ), patch(
        "mastr_data_pipeline.bq_raw.replace_all_snapshots_atomically"
    ) as replace:
        with pytest.raises(ValueError, match="Row count mismatch"):
            load_snapshot_to_raw(
                project_id="proj",
                bucket="bucket",
                snapshot_date="2026-11-09",
                dataset="mastr_raw",
                location="europe-west3",
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
            staging_tables=_split_staging_tables(),
        )

    assert load_tmp.call_count == 4
    assert set(counts) == set(SOURCE_FILES)
    assert client.query.call_count == 4
