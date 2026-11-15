.PHONY: install format test generate-snapshot-seed

install:
	poetry install

format:
	poetry run black .

test:
	PYTHONDONTWRITEBYTECODE=1 poetry run pytest tests -m "not optional" -v --disable-warnings --color=yes

# Regenerate dbt/seeds/seed_snapshot_expectations.csv from config/snapshots.json
# (single source of truth). Run before `dbt seed` when snapshot expectations change.
generate-snapshot-seed:
	poetry run python scripts/generate_snapshot_expectations_seed.py
