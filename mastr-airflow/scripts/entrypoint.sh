#!/usr/bin/env bash
# Webserver entrypoint: migrate metadata DB, ensure admin user, start UI.
set -euo pipefail

cd "${AIRFLOW_PROJECT:-/opt/airflow-project}"

poetry run airflow db migrate

poetry run airflow users create \
  --role Admin \
  --username "${AIRFLOW_ADMIN_USER:-admin}" \
  --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
  --email "${AIRFLOW_ADMIN_EMAIL:-admin@example.com}" \
  --firstname Admin \
  --lastname User \
  || true

exec poetry run airflow webserver
