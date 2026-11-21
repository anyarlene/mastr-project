"""Tests for dashboard project configuration and ADC-based BigQuery client setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import utils.bigquery as bq


def setup_function() -> None:
    bq.get_client.cache_clear()
    bq._ENV_LOADED = False


def teardown_function() -> None:
    bq.get_client.cache_clear()
    bq._ENV_LOADED = False


def test_default_project_id_constant() -> None:
    assert bq.DEFAULT_PROJECT_ID == "mastr-project-1126"
    assert bq.DATASET == "mastr_marts"
    assert bq.LOCATION == "europe-west3"


def test_get_project_id_uses_default_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with patch.object(bq, "_load_env"):
        assert bq.get_project_id() == "mastr-project-1126"


def test_get_project_id_respects_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "my-team-gcp-project")
    with patch.object(bq, "_load_env"):
        assert bq.get_project_id() == "my-team-gcp-project"


def test_get_client_uses_adc_not_service_account_json(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "override-project")
    fake_client = MagicMock(name="BigQueryClient")

    with (
        patch.object(bq, "_load_env"),
        patch.object(bq.bigquery, "Client", return_value=fake_client) as client_ctor,
        patch.object(
            bq.bigquery.Client,
            "from_service_account_json",
            create=True,
        ) as from_sa,
    ):
        result = bq.get_client()

    assert result is fake_client
    client_ctor.assert_called_once_with(project="override-project", location="europe-west3")
    from_sa.assert_not_called()


def test_sql_builders_use_configured_project(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "sql-project-xyz")
    captured: list[str] = []

    def fake_run_query(sql: str):
        captured.append(sql)
        return MagicMock()

    with (
        patch.object(bq, "_load_env"),
        patch.object(bq, "run_query", side_effect=fake_run_query),
    ):
        bq.load_municipality_capacity()
        bq.load_capacity_by_energy_source()

    assert len(captured) == 2
    assert all("sql-project-xyz.mastr_marts." in sql for sql in captured)
    assert all("wagon-bootcamp" not in sql for sql in captured)
    assert "mart_municipality_capacity" in captured[0]
    assert "fct_mastr_units" in captured[1]
    assert "dim_energy_source" in captured[1]
    assert "f.energy_source_id = e.energy_source_id" in captured[1]
    assert "f.snapshot_date = m.snapshot_date" in captured[1]
    assert "f.municipality_id = m.municipality_id" in captured[1]


def test_dashboard_files_have_no_legacy_bootcamp_paths() -> None:
    root = bq.Path(__file__).resolve().parents[1]
    targets = [
        root / "utils" / "bigquery.py",
        root / ".env.example",
        root / "README.md",
    ]
    forbidden = (
        "your-gcp-project-id",
        "/home/YOUR_USER",
        "~/.gcp_keys/",
        "from_service_account_json",
        "dbt-service-account.json",
    )
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{needle!r} found in {path.name}"
