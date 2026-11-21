"""Static checks for the MaStR orchestration DAG (no Airflow/DB required)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DAG_FILE = REPO / "dags" / "mastr_snapshot_pipeline.py"

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
