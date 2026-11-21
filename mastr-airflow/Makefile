.PHONY: install format test compose-config

install:
	poetry install --with dev

format:
	poetry run black .

test:
	PYTHONDONTWRITEBYTECODE=1 poetry run pytest tests -m "not optional" -v --disable-warnings --color=yes

# Validate Compose file interpolation (requires a local .env; does not start services)
compose-config:
	docker compose config --quiet
