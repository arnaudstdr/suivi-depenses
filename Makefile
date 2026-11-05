.PHONY: install dev lint format typecheck test db-up db-down migrate revision check-migrations

install:
	cd backend && uv sync --frozen

dev:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format app tests migrations

typecheck:
	cd backend && uv run mypy app

test:
	cd backend && uv run pytest -q

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

revision:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

check-migrations:
	cd backend && uv run alembic check
