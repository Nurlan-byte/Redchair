from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions import AuthenticationError, ConflictError

_UNIQUE_TO_ERROR = {
    "uq_users_email": ("email_taken", "Email already registered"),
    "uq_users_username": ("username_taken", "Username already registered"),
}


async def register_user(
    session: AsyncSession, *, username: str, email: str, password: str
) -> models.User:
    user = models.User(username=username, email=email, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as e:
        constraint = getattr(getattr(e.orig, "__cause__", None), "constraint_name", None)
        if constraint in _UNIQUE_TO_ERROR:
            raise ConflictError(*_UNIQUE_TO_ERROR[constraint]) from e
        raise
    session.add(models.Diary(user_id=user.id))
    return user


async def login(session: AsyncSession, *, email: str, password: str) -> str:
    user = await session.scalar(select(models.User).where(models.User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid_credentials", "Invalid credentials")
    return create_access_token(data={"user_id": user.id})
