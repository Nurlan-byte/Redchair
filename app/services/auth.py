from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions import AuthenticationError, ConflictError


async def register_user(
    session: AsyncSession, *, username: str, email: str, password: str
) -> models.User:
    email_taken = await session.scalar(select(models.User.id).where(models.User.email == email))
    if email_taken is not None:
        raise ConflictError("email_taken", "Email already registered")

    username_taken = await session.scalar(
        select(models.User.id).where(models.User.username == username)
    )
    if username_taken is not None:
        raise ConflictError("username_taken", "Username already registered")

    user = models.User(username=username, email=email, password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    session.add(models.Diary(user_id=user.id))
    return user


async def login(session: AsyncSession, *, email: str, password: str) -> str:
    user = await session.scalar(select(models.User).where(models.User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid_credentials", "Invalid credentials")
    return create_access_token(data={"user_id": user.id})
