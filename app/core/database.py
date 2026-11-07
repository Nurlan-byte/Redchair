from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.exceptions import AppError

from .config import settings

engine = create_async_engine(settings.sqlalchemy_url, pool_pre_ping=True, pool_recycle=1800)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


async def open_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_db(session: AsyncSession = Depends(open_session)) -> AsyncIterator[AsyncSession]:
    try:
        yield session
        await session.commit()
    except AppError as e:
        await (session.commit() if e.commit_before_raise else session.rollback())
        raise
    except Exception:
        await session.rollback()
        raise


DbSession = Annotated[AsyncSession, Depends(get_db)]
