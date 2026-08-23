# Redchair

![CI](https://github.com/Nurlan-byte/Redchair/actions/workflows/ci.yml/badge.svg)

Social habit tracker API.
FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · Pydantic v2 · JWT · pytest

## Setup

Requires Docker, Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
docker compose up -d            # postgres for development (5434) and tests (5433)
uv sync
cp .env.example .env            # Windows: copy .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Fill in `.env` first. Generate `SECRET_KEY` with
`python -c "import secrets; print(secrets.token_hex(32))"`.

If port 5434 is already in use, change the host port in the `db` service in
`docker-compose.yml` and update `DATABASE_URL` in `.env` to match.
The test database port (5433) is set in `docker-compose.yml` and `pyproject.toml`.

Swagger UI: http://127.0.0.1:8000/docs

## Tests

```bash
uv run pytest
```

Tests run against a separate throwaway PostgreSQL container. The schema is
rebuilt from migrations on every run; each test runs in a transaction that is
rolled back afterwards.
