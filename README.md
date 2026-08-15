# Redchair

Social habit tracker API. Users keep a diary of goals, log daily progress,
follow each other and see entries in a feed.

## Requirements

- Python 3.14
- PostgreSQL

## Getting started

Create two databases — one for the app, one for tests:

```sql
CREATE DATABASE redchair;
CREATE DATABASE redchair_test;
```

Install dependencies and set up the environment:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env            # Windows: copy .env.example .env
```

Open `.env` and fill in your values. Generate `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Run migrations and start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

## API documentation

Once running, Swagger UI is available at http://127.0.0.1:8000/docs

## Tech stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · Pydantic v2 · JWT · pytest