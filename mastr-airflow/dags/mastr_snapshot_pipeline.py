"""
MaStR snapshot orchestration DAG.

Triggers the validated pipeline in mastr-data-pipeline for one snapshot_date:
  check CSVs → Bronze → Raw → snapshot seed → dbt seed → dbt run → dbt test

No business logic lives here — tasks shell out to the existing CLI / Makefile
equivalents via scripts/run_pipeline.sh and the isolated pipeline venv.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

PIPELINE_DIR = os.environ.get("MASTR_PIPELINE_DIR", "/opt/mastr-data-pipeline")
RUN_PIPELINE = "/opt/airflow-project/scripts/run_pipeline.sh"
SOURCE_FILES = ("wind.csv", "solar.csv", "biomass.csv", "battery.csv")
SNAPSHOT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_ARGS = {
    "owner": "mastr",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _snapshot_date(context) -> str:
    params = context.get("params") or {}
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    value = conf.get("snapshot_date") or params.get("snapshot_date")
    if not value:
        raise ValueError(
            "snapshot_date is required (DAG param or dag_run.conf.snapshot_date)"
        )
    return str(value)


def check_local_csvs(**context) -> str:
    """Validate snapshot_date format, config presence, and the four local CSVs."""
    snapshot_date = _snapshot_date(context)
    if not SNAPSHOT_DATE_RE.match(snapshot_date):
        raise ValueError(f"snapshot_date must be YYYY-MM-DD, got {snapshot_date!r}")

    datetime.strptime(snapshot_date, "%Y-%m-%d")

    pipeline = Path(PIPELINE_DIR)
    snapshots_path = pipeline / "config" / "snapshots.json"
    if not snapshots_path.is_file():
        raise FileNotFoundError(f"Missing snapshot config: {snapshots_path}")

    payload = json.loads(snapshots_path.read_text(encoding="utf-8"))
    known = payload.get("snapshots") or {}
    if snapshot_date not in known:
        raise ValueError(
            f"snapshot_date {snapshot_date!r} is not present in "
            f"{snapshots_path}. Add SHA-256 and row_counts before running."
        )

    folder = Path(os.environ.get("MASTR_RAW_DIR", str(pipeline / "data" / "raw")))
    snap_dir = folder / snapshot_date
    if not snap_dir.is_dir():
        raise FileNotFoundError(
            f"Snapshot folder not found: {snap_dir}. "
            "Place the four CSVs under data/raw/<snapshot_date>/ (manual download)."
        )

    missing = [name for name in SOURCE_FILES if not (snap_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing CSV(s) in {snap_dir}: {missing}")

    return snapshot_date


with DAG(
    dag_id="mastr_snapshot_pipeline",
    description=(
        "Orchestrate MaStR Bronze → Raw → dbt for one manual snapshot_date"
    ),
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 11, 9),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["mastr", "snapshot"],
    params={
        "snapshot_date": Param(
            default="2026-11-09",
            type="string",
            title="Snapshot date",
            description=(
                "Folder label under data/raw/YYYY-MM-DD "
                "(must exist in config/snapshots.json)."
            ),
        ),
    },
    doc_md=__doc__,
) as dag:
    check = PythonOperator(
        task_id="check_local_csvs",
        python_callable=check_local_csvs,
        retries=0,
    )

    ingest_bronze = BashOperator(
        task_id="ingest_bronze",
        bash_command=(
            "set -euo pipefail; "
            'SNAPSHOT_DATE="{{ ti.xcom_pull(task_ids=\'check_local_csvs\') }}"; '
            f'"{RUN_PIPELINE}" ingest-bronze "$SNAPSHOT_DATE"'
        ),
    )

    load_raw = BashOperator(
        task_id="load_raw",
        bash_command=(
            "set -euo pipefail; "
            'SNAPSHOT_DATE="{{ ti.xcom_pull(task_ids=\'check_local_csvs\') }}"; '
            f'"{RUN_PIPELINE}" load-raw "$SNAPSHOT_DATE"'
        ),
    )

    generate_snapshot_seed = BashOperator(
        task_id="generate_snapshot_seed",
        bash_command=f'set -euo pipefail; "{RUN_PIPELINE}" generate-snapshot-seed',
        retries=1,
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f'set -euo pipefail; "{RUN_PIPELINE}" dbt-seed',
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f'set -euo pipefail; "{RUN_PIPELINE}" dbt-run',
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f'set -euo pipefail; "{RUN_PIPELINE}" dbt-test',
        retries=1,
    )

    (
        check
        >> ingest_bronze
        >> load_raw
        >> generate_snapshot_seed
        >> dbt_seed
        >> dbt_run
        >> dbt_test
    )
