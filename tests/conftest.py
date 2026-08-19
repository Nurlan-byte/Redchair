import asyncio

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from app import models, oauth2
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from tests import constants

print(f"\nDB: {make_url(settings.sqlalchemy_url).render_as_string(hide_password=False)}")

db_name = make_url(settings.sqlalchemy_url).database or ""
if not db_name.endswith("_test"):
    pytest.exit(f"refusing to run: {db_name} is not a test database", returncode=1)


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.sqlalchemy_url)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)
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
    async def override_get_db():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_users(session):
    USERNAMES = [
        "aspas",
        "penguin",
        "ronaldo",
        "neymar",
        "haaland",
        "mbappe",
        "modric",
        "debruyne",
        "pedri",
        "bellingham",
    ]
    users = [
        models.User(
            username=u,
            email=f"{u}@gmail.com",
            password_hash=constants.TEST_PASSWORD_HASH,
        )
        for u in USERNAMES
    ]
    session.add_all(users)
    await session.commit()

    return users


@pytest_asyncio.fixture
async def authorized_client(client, test_users):
    token = oauth2.create_access_token(data={"user_id": test_users[0].id})
    client.headers["Authorization"] = f"Bearer {token}"
    return client
