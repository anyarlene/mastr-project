
.PHONY: install run test build up down logs ps

install:
	poetry install

run:
	poetry run streamlit run app.py

test:
	poetry run pytest -v

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f dashboard

ps:
	docker compose ps
