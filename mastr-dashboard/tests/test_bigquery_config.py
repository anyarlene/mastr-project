"""Tests for dashboard project configuration and ADC-based BigQuery client setup."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

import utils.bigquery as bq

# Placeholder usernames allowed in samples; reject any other /home/<name> path.
_ALLOWED_HOME_USERS = frozenset({"YOUR_USER"})
_HOME_USER_RE = re.compile(r"/home/([A-Za-z0-9._-]+)")
# Reject service-account JSON key paths and common private-key filenames.
_UNSAFE_CREDENTIAL_PATH_RE = re.compile(
    r"(?:~|/home/[A-Za-z0-9._-]+)/\.gcp_keys(?:/|\b)|dbt-service-account\.json"
)
# Stand-in non-placeholder project id that must not appear in samples or SQL.
_FORBIDDEN_SAMPLE_PROJECT_ID = "test-mastr-project"


def setup_function() -> None:
    bq.get_client.cache_clear()
    bq._ENV_LOADED = False


def teardown_function() -> None:
    bq.get_client.cache_clear()
    bq._ENV_LOADED = False


def _assert_no_hardcoded_personal_homes(text: str, *, label: str) -> None:
    for match in _HOME_USER_RE.finditer(text):
        user = match.group(1)
        assert user in _ALLOWED_HOME_USERS, (
            f"{label}: hardcoded personal home path {match.group(0)!r}"
        )


def test_product_marts_dataset_default() -> None:
    assert bq.DEFAULT_MARTS_DATASET == "mastr_marts"


def test_get_project_id_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with patch.object(bq, "_load_env"):
        with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
            bq.get_project_id()


def test_get_location_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    with patch.object(bq, "_load_env"):
        with pytest.raises(ValueError, match="BQ_LOCATION"):
            bq.get_location()


def test_get_project_id_and_location_respect_env(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "my-team-gcp-project")
    monkeypatch.setenv("BQ_LOCATION", "europe-west3")
    with patch.object(bq, "_load_env"):
        assert bq.get_project_id() == "my-team-gcp-project"
        assert bq.get_location() == "europe-west3"


def test_get_marts_dataset_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("BQ_MARTS_DATASET", raising=False)
    with patch.object(bq, "_load_env"):
        assert bq.get_marts_dataset() == "mastr_marts"
    monkeypatch.setenv("BQ_MARTS_DATASET", "custom_marts")
    with patch.object(bq, "_load_env"):
        assert bq.get_marts_dataset() == "custom_marts"


def test_get_client_uses_adc_not_service_account_json(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "override-project")
    monkeypatch.setenv("BQ_LOCATION", "europe-west3")
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


def test_sql_builders_use_configured_project_and_dataset(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "sql-project-xyz")
    monkeypatch.setenv("BQ_LOCATION", "europe-west3")
    monkeypatch.setenv("BQ_MARTS_DATASET", "mastr_marts")
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
    assert all(_FORBIDDEN_SAMPLE_PROJECT_ID not in sql for sql in captured)
    assert "mart_municipality_capacity" in captured[0]
    assert "fct_mastr_units" in captured[1]
    assert "dim_energy_source" in captured[1]
    assert "f.energy_source_id = e.energy_source_id" in captured[1]
    assert "f.snapshot_date = m.snapshot_date" in captured[1]
    assert "f.municipality_id = m.municipality_id" in captured[1]


def test_dashboard_files_have_no_unsafe_auth_or_personal_paths() -> None:
    root = bq.Path(__file__).resolve().parents[1]
    targets = [
        root / "utils" / "bigquery.py",
        root / ".env.sample",
        root / "README.md",
    ]
    forbidden_literals = (
        "from_service_account_json",
        "dbt-service-account.json",
        "~/.gcp_keys/",
        _FORBIDDEN_SAMPLE_PROJECT_ID,
    )
    for path in targets:
        text = path.read_text(encoding="utf-8")
        label = path.name
        for needle in forbidden_literals:
            assert needle not in text, f"{needle!r} found in {label}"
        assert _UNSAFE_CREDENTIAL_PATH_RE.search(text) is None, (
            f"unsafe service-account key path found in {label}"
        )
        _assert_no_hardcoded_personal_homes(text, label=label)
