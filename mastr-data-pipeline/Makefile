.PHONY: install format test generate-snapshot-seed dbt-parse dbt-seed dbt-run dbt-test

# dbt project lives under ./dbt; profile `mastr` is in ~/.dbt/profiles.yml
DBT_PROJECT_DIR := dbt
DBT_PROFILES_DIR := $(HOME)/.dbt

install:
	poetry install --with dbt

format:
	poetry run black .

test:
	PYTHONDONTWRITEBYTECODE=1 poetry run pytest tests -m "not optional" -v --disable-warnings --color=yes

# Regenerate snapshot seeds from config/snapshots.json (single source of truth):
#   seed_snapshot_expectations.csv + seed_snapshot_metadata.csv
# Run before `make dbt-seed` when snapshot registration changes.
generate-snapshot-seed:
	poetry run python scripts/generate_snapshot_expectations_seed.py

# Validate dbt project / refs (no BigQuery writes)
dbt-parse:
	poetry run dbt parse --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

# Load reference seeds into BigQuery (mastr_staging)
dbt-seed:
	poetry run dbt seed --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

# Build Staging, Intermediate, and Gold models
dbt-run:
	poetry run dbt run --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

# Run all dbt data tests
dbt-test:
	poetry run dbt test --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)
