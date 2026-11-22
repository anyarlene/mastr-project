# Airflow runtime + isolated MaStR pipeline dependency venv (multi-stage).
# Build context: this repository (mastr-airflow). Pipeline *source* is mounted
# at runtime; only dependency pins are baked in (container/pipeline-requirements.txt).
# Do not COPY ADC, JSON keys, or .env into the image.
#
# Builder installs compilers; the runtime stage keeps only runtime OS packages
# (curl for healthchecks) plus Poetry and the two prebuilt virtualenvs.

ARG PYTHON_IMAGE=python:3.12.8-slim

# ---------------------------------------------------------------------------
# Builder: compile / install Python dependencies
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    AIRFLOW_HOME=/opt/airflow \
    AIRFLOW_PROJECT=/opt/airflow-project \
    MASTR_PIPELINE_DIR=/opt/mastr-data-pipeline \
    PIPELINE_VENV=/opt/venvs/mastr-pipeline \
    DBT_PROFILES_DIR=/opt/dbt \
    MASTR_RAW_DIR=/opt/mastr-data-pipeline/data/raw \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip poetry \
    && mkdir -p \
        /opt/airflow/dags \
        /opt/airflow/logs \
        /opt/venvs \
        /opt/dbt \
        /opt/mastr-data-pipeline \
        /root/.config/gcloud

# --- Airflow Poetry environment (scheduler / webserver only) ---
WORKDIR ${AIRFLOW_PROJECT}
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# --- Isolated pipeline dependency venv (no host Poetry, no Airflow pkgs) ---
COPY container/pipeline-requirements.txt /tmp/pipeline-requirements.txt
RUN python -m venv ${PIPELINE_VENV} \
    && ${PIPELINE_VENV}/bin/pip install --no-cache-dir --upgrade pip \
    && ${PIPELINE_VENV}/bin/pip install --no-cache-dir -r /tmp/pipeline-requirements.txt \
    && rm -f /tmp/pipeline-requirements.txt

COPY scripts/entrypoint.sh scripts/run_pipeline.sh ./scripts/
RUN chmod +x scripts/entrypoint.sh scripts/run_pipeline.sh

# ---------------------------------------------------------------------------
# Runtime: no compilers; reuse builder virtualenvs
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    AIRFLOW_HOME=/opt/airflow \
    AIRFLOW_PROJECT=/opt/airflow-project \
    MASTR_PIPELINE_DIR=/opt/mastr-data-pipeline \
    PIPELINE_VENV=/opt/venvs/mastr-pipeline \
    DBT_PROFILES_DIR=/opt/dbt \
    MASTR_RAW_DIR=/opt/mastr-data-pipeline/data/raw \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PATH="/opt/airflow-project/.venv/bin:${PATH}"

# curl: Compose healthchecks. Poetry: existing `poetry run airflow …` commands.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip poetry \
    && mkdir -p \
        /opt/airflow/dags \
        /opt/airflow/logs \
        /opt/venvs \
        /opt/dbt \
        /opt/mastr-data-pipeline \
        /root/.config/gcloud

COPY --from=builder /opt/airflow-project /opt/airflow-project
COPY --from=builder /opt/venvs/mastr-pipeline /opt/venvs/mastr-pipeline

WORKDIR ${AIRFLOW_PROJECT}
