# Airflow runtime + isolated MaStR pipeline dependency venv.
# Build context: this repository (mastr-airflow). Pipeline *source* is mounted
# at runtime; only dependency pins are baked in (container/pipeline-requirements.txt).
FROM python:3.12.8-slim

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    AIRFLOW_HOME=/opt/airflow \
    AIRFLOW_PROJECT=/opt/airflow-project \
    MASTR_PIPELINE_DIR=/opt/mastr-data-pipeline \
    PIPELINE_VENV=/opt/venvs/mastr-pipeline \
    DBT_PROFILES_DIR=/home/YOUR_USER/.dbt \
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
        /home/YOUR_USER \
        /opt/mastr-data-pipeline \
    && chmod 755 /home/YOUR_USER

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

# Default PATH prefers Airflow poetry env for `poetry run airflow …`
ENV PATH="${AIRFLOW_PROJECT}/.venv/bin:${PATH}"

WORKDIR ${AIRFLOW_PROJECT}
