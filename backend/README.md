# Backend — Suivi de dépenses

API FastAPI, SQLAlchemy 2 et Alembic, adossée à PostgreSQL.

## Prérequis

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker et Docker Compose

## Installation

Depuis la racine du dépôt :

```bash
cp .env.example .env
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
```

## Démarrage

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alternative conteneurisée (PostgreSQL + API) :

```bash
docker compose --profile docker up -d --build api
```

Endpoints disponibles :

- `GET /health/live` : le processus répond.
- `GET /health/ready` : PostgreSQL est joignable.
- `GET /docs` : documentation OpenAPI, si `DOCS_ENABLED=true`.

## Contrôles

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q -m unit
TEST_DATABASE_URL=postgresql+psycopg://suivi:change-me-local-only@127.0.0.1:5432/suivi_depenses_test \
  uv run pytest -q
```

Les tests d'intégration créent et suppriment leurs propres bases temporaires à
partir de `TEST_DATABASE_URL`. L'utilisateur PostgreSQL doit donc pouvoir créer
des bases.

## Migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run alembic revision --autogenerate -m "description"
```

La première migration crée `users`, `households` et `household_members`.
Les tables d'authentification (`sessions`, `invitations`, `audit_logs`) seront
ajoutées avec la tranche « socle sécurisé ».
