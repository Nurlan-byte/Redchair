from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.exceptions import NotFoundError


async def list_users(
    session: AsyncSession, *, limit: int, offset: int, username: str | None = None
) -> tuple[Sequence[models.User], bool]:
    stmt = select(models.User).where(models.User.deleted_at.is_(None))
    if username:
        stmt = stmt.where(models.User.username.icontains(username, autoescape=True))
    res = await session.scalars(
        stmt.order_by(models.User.id.desc()).limit(limit + 1).offset(offset)
    )
    users = res.all()
    return users[:limit], len(users) > limit


async def get_user_by_username(session: AsyncSession, *, username: str) -> models.User:
    user = await session.scalar(
        select(models.User).where(
            models.User.username == username, models.User.deleted_at.is_(None)
        )
    )
    if user is None:
        raise NotFoundError("user_not_found", f"User with username: {username} does not exist")
    return user
