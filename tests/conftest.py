import asyncio

import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from app import models
from app.core.config import settings
from app.core.database import get_db
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.test_sqlalchemy_url)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.test_sqlalchemy_url)
    await asyncio.to_thread(command.downgrade, cfg, "base")
    await asyncio.to_thread(command.upgrade, cfg, "head")

    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        db = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield db
        await db.close()
        await trans.rollback()


@pytest_asyncio.fixture
async def client(session):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_users(session):
    users_data = [
        {"username": "aspas", "email": "aspas@gmail.com", "password_hash": "ASpas123"},
        {"username": "messi", "email": "messi@gmail.com", "password_hash": "Messi123"},
        {"username": "ronaldo", "email": "ronaldo@gmail.com", "password_hash": "Ronaldo123"},
        {"username": "neymar", "email": "neymar@gmail.com", "password_hash": "Neymar123"},
        {"username": "haaland", "email": "haaland@gmail.com", "password_hash": "Haaland123"},
        {"username": "mbappe", "email": "mbappe@gmail.com", "password_hash": "Mbappe123"},
        {"username": "modric", "email": "modric@gmail.com", "password_hash": "Modric123"},
        {
            "username": "debruyne",
            "email": "debruyne@gmail.com",
            "password_hash": "DeBruyne123",
        },
        {"username": "pedri", "email": "pedri@gmail.com", "password_hash": "Pedri123"},
        {
            "username": "bellingham",
            "email": "bellingham@gmail.com",
            "password_hash": "Bellingham123",
        },
    ]

    users = [models.User(**u) for u in users_data]
    session.add_all(users)
    await session.commit()

    result = await session.execute(select(models.User))
    return result.scalars().all()
