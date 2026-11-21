"""Tests for Raw schema helpers (no GCP)."""

from __future__ import annotations

import pytest

from mastr_data_pipeline.raw_schema import (
    GERMAN_HEADERS,
    UNIT_ID_FIELD,
    expected_row_counts,
    payload_field_names,
    raw_table_schema_fields,
    sanitize_field_name,
)


def test_german_headers_count_and_unique_sanitized_names():
    assert len(GERMAN_HEADERS) == 64
    names = payload_field_names()
    assert len(names) == 64
    assert len(set(names)) == 64


def test_unit_id_field_name():
    assert UNIT_ID_FIELD == sanitize_field_name("MaStR-Nr. der Einheit")
    assert UNIT_ID_FIELD == "mastr_nr_der_einheit"


def test_raw_table_schema_includes_lineage_as_non_string_types():
    schema = raw_table_schema_fields()
    by_name = {f["name"]: f for f in schema}
    assert len(schema) == 67
    assert all(by_name[n]["type"] == "STRING" for n in payload_field_names())
    assert by_name["source_file"]["type"] == "STRING"
    assert by_name["snapshot_date"]["type"] == "DATE"
    assert by_name["ingested_at"]["type"] == "TIMESTAMP"


def test_expected_row_counts_2026_11_09():
    counts = expected_row_counts("2026-11-09")
    assert counts == {
        "wind.csv": 278,
        "solar.csv": 20_861,
        "biomass.csv": 56,
        "battery.csv": 11_416,
    }
    assert sum(counts.values()) == 32_611


def test_expected_row_counts_unknown():
    with pytest.raises(ValueError, match="No expected row counts"):
        expected_row_counts("1999-01-01")
