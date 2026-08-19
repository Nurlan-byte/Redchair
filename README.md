# Redchair

Social habit tracker API.

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · Pydantic v2 · JWT · pytest

## Setup

Requires Python 3.12, PostgreSQL and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sql
CREATE DATABASE redchair;
CREATE DATABASE redchair_test;
```

```bash
uv sync
cp .env.example .env            # Windows: copy .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Fill in `.env` first. Generate `SECRET_KEY` with
`python -c "import secrets; print(secrets.token_hex(32))"`.

Swagger UI: http://127.0.0.1:8000/docs

## Tests

Run from the repository root. Tests need a real PostgreSQL —
`TEST_DATABASE_URL` is read by the test suite only, not by the app.

```bash
uv run pytest
```
