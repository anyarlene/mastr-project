#!/usr/bin/env bash
# Run MaStR pipeline CLI / Makefile-equivalent commands with the isolated
# container venv (not the host Poetry environment, not the Airflow venv).
set -euo pipefail

PIPELINE_DIR="${MASTR_PIPELINE_DIR:?MASTR_PIPELINE_DIR is required}"
VENV="${PIPELINE_VENV:?PIPELINE_VENV is required}"
PROFILES_DIR="${DBT_PROFILES_DIR:-${HOME}/.dbt}"

export PATH="${VENV}/bin:${PATH}"
export PYTHONPATH="${PIPELINE_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
export DBT_PROFILES_DIR="${PROFILES_DIR}"

cd "${PIPELINE_DIR}"

cmd="${1:?usage: run_pipeline.sh <command> [snapshot_date]}"
shift || true

case "${cmd}" in
  check-local-csvs)
    # Implemented in the DAG Python callable; kept for symmetry/docs.
    echo "use DAG task check_local_csvs" >&2
    exit 2
    ;;
  ingest-bronze)
    snapshot_date="${1:?snapshot_date required}"
    exec python -m mastr_data_pipeline ingest-bronze --snapshot-date "${snapshot_date}"
    ;;
  load-raw)
    snapshot_date="${1:?snapshot_date required}"
    exec python -m mastr_data_pipeline load-raw --snapshot-date "${snapshot_date}"
    ;;
  generate-snapshot-seed)
    # Same as: make generate-snapshot-seed
    exec python scripts/generate_snapshot_expectations_seed.py
    ;;
  dbt-seed)
    # Same as: make dbt-seed
    exec dbt seed --project-dir dbt --profiles-dir "${PROFILES_DIR}"
    ;;
  dbt-run)
    # Same as: make dbt-run
    exec dbt run --project-dir dbt --profiles-dir "${PROFILES_DIR}"
    ;;
  dbt-test)
    # Same as: make dbt-test
    exec dbt test --project-dir dbt --profiles-dir "${PROFILES_DIR}"
    ;;
  *)
    echo "unknown command: ${cmd}" >&2
    echo "known: ingest-bronze | load-raw | generate-snapshot-seed | dbt-seed | dbt-run | dbt-test" >&2
    exit 2
    ;;
esac
