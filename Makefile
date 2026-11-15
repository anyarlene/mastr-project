.PHONY: install format test

install:
	poetry install

format:
	poetry run black .

test:
	PYTHONDONTWRITEBYTECODE=1 poetry run pytest tests -m "not optional" -v --disable-warnings --color=yes
