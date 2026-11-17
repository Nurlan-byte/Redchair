import asyncio
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app import models
from app.core.config import settings
from app.core.database import open_session
from app.core.security import create_access_token
from app.main import app
from tests import constants

print(f"\nDB: {make_url(settings.sqlalchemy_url).render_as_string(hide_password=True)}")

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


@pytest.fixture
def query_counter(engine):
    """Collects data statements only: the savepoint fixture adds SAVEPOINT/RELEASE noise."""
    statements: list[str] = []

    def collect(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", collect)
    yield statements
    event.remove(engine.sync_engine, "before_cursor_execute", collect)


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
    async def override_open_session():
        yield session

    app.dependency_overrides[open_session] = override_open_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def committing_client(engine):
    """Every request gets its own session and really commits; the test must clean up."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def fresh_session():
        async with sessions() as db:
            yield db

    app.dependency_overrides[open_session] = fresh_session
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
    await session.flush()
    # Registration always creates a diary; fixtures keep the same invariant.
    session.add_all(models.Diary(user_id=user.id) for user in users)
    await session.commit()

    return users


@pytest_asyncio.fixture
async def deleted_user(session, test_users):
    user = test_users[-1]
    user.deleted_at = datetime.now(UTC)
    await session.commit()
    return user


@pytest_asyncio.fixture
async def authorized_client(client, test_users):
    token = create_access_token(test_users[0].id)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def make_goals(session):
    async def make(user: models.User, count: int = 1) -> list[models.Goal]:
        diary_id = await session.scalar(
            select(models.Diary.id).where(models.Diary.user_id == user.id)
        )
        goals = [
            models.Goal(diary_id=diary_id, title=f"Goal {i}", statistic=models.GoalStatistic())
            for i in range(count)
        ]
        session.add_all(goals)
        await session.flush()
        return goals

    return make
