"""Static checks for the MaStR orchestration DAG (no Airflow/DB required)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DAG_FILE = REPO / "dags" / "mastr_snapshot_pipeline.py"

# Placeholder usernames allowed in samples; reject any other /home/<name> path.
_ALLOWED_HOME_USERS = frozenset({"YOUR_USER"})
_HOME_USER_RE = re.compile(r"/home/([A-Za-z0-9._-]+)")


def _assert_no_hardcoded_personal_homes(text: str, *, label: str) -> None:
    for match in _HOME_USER_RE.finditer(text):
        user = match.group(1)
        assert user in _ALLOWED_HOME_USERS, (
            f"{label}: hardcoded personal home path {match.group(0)!r}"
        )

EXPECTED_TASKS = [
    "check_local_csvs",
    "ingest_bronze",
    "load_raw",
    "generate_snapshot_seed",
    "dbt_seed",
    "dbt_run",
    "dbt_test",
]


def test_dag_file_defines_expected_task_ids():
    tree = ast.parse(DAG_FILE.read_text(encoding="utf-8"))
    task_ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "task_id" and isinstance(kw.value, ast.Constant):
                    task_ids.add(kw.value.value)
    assert task_ids == set(EXPECTED_TASKS)


def test_dag_dependency_chain_order_in_source():
    text = DAG_FILE.read_text(encoding="utf-8")
    # Bitshift chain must appear in order in the source.
    needle = (
        "check\n"
        "        >> ingest_bronze\n"
        "        >> load_raw\n"
        "        >> generate_snapshot_seed\n"
        "        >> dbt_seed\n"
        "        >> dbt_run\n"
        "        >> dbt_test"
    )
    assert needle in text


def test_dag_is_manual_and_single_active_run():
    text = DAG_FILE.read_text(encoding="utf-8")
    assert "schedule=None" in text
    assert "max_active_runs=1" in text
    assert 'dag_id="mastr_snapshot_pipeline"' in text


def test_run_pipeline_script_covers_makefile_equivalents():
    script = (REPO / "scripts" / "run_pipeline.sh").read_text(encoding="utf-8")
    for cmd in (
        "ingest-bronze",
        "load-raw",
        "generate-snapshot-seed",
        "dbt-seed",
        "dbt-run",
        "dbt-test",
    ):
        assert cmd in script


def test_compose_mentions_isolated_pipeline_venv_and_no_host_venv_mount():
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "/opt/venvs/mastr-pipeline" in compose
    assert "../mastr-data-pipeline:/opt/mastr-data-pipeline" in compose
    # No bind-mount of a host Poetry virtualenv; comments may mention .venv.
    assert "/.venv:" not in compose
    assert ".venv:" not in compose
    assert "docker.sock" not in compose


def test_compose_uses_keyless_adc_and_portable_paths():
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    env_sample = (REPO / ".env.sample").read_text(encoding="utf-8")

    # ADC file mount at the container well-known path for root.
    assert (
        "${GCP_ADC_HOST_PATH}:/root/.config/gcloud/"
        "application_default_credentials.json:ro" in compose
    )
    assert "DBT_PROFILES_DIR: /opt/dbt" in compose
    assert "${DBT_PROFILES_HOST_PATH}:/opt/dbt:ro" in compose

    # No forced JSON key auth or hardcoded personal home directories.
    assert "GOOGLE_APPLICATION_CREDENTIALS:" not in compose
    assert "GOOGLE_APPLICATION_CREDENTIALS=" not in compose
    assert "gcp_keys" not in compose
    assert "GCP_KEYS_HOST_PATH" not in compose
    assert "dbt-service-account.json" not in compose
    _assert_no_hardcoded_personal_homes(compose, label="docker-compose.yml")

    assert "DBT_PROFILES_DIR=/opt/dbt" in dockerfile
    assert "dbt-service-account.json" not in dockerfile
    _assert_no_hardcoded_personal_homes(dockerfile, label="Dockerfile")

    assert "GCP_ADC_HOST_PATH=" in env_sample
    assert "GCP_KEYS_HOST_PATH" not in env_sample
    assert "GOOGLE_APPLICATION_CREDENTIALS=" not in env_sample
    assert "your-gcp-project-id" in env_sample
    assert "test-mastr-project" not in env_sample
    assert "dbt-service-account.json" not in env_sample
    _assert_no_hardcoded_personal_homes(env_sample, label=".env.sample")
