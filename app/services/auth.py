import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainValidationError,
    RefreshTokenReusedError,
)

# "me" would be shadowed by GET /users/me, so nobody could open that profile.
RESERVED_USERNAMES = frozenset({"me"})


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


_UNIQUE_TO_ERROR = {
    "uq_users_email": ("email_taken", "Email already registered"),
    "uq_users_username": ("username_taken", "Username already registered"),
}


async def register_user(
    session: AsyncSession, *, username: str, email: str, password: str, timezone: str = "UTC"
) -> models.User:
    if username in RESERVED_USERNAMES:
        raise DomainValidationError("username_reserved", f"Username {username!r} is reserved")

    # EmailStr lowercases only the domain; the local part keeps its case.
    email = email.lower()
    user = models.User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        timezone=timezone,
    )
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


async def login(session: AsyncSession, *, email: str, password: str) -> TokenPair:
    user = await session.scalar(
        select(models.User).where(
            models.User.email == email.lower(), models.User.deleted_at.is_(None)
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid_credentials", "Invalid credentials")
    refresh_token = _issue_refresh_token(session, user_id=user.id, family_id=uuid.uuid4())
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh_token)


async def refresh(session: AsyncSession, *, refresh_token: str) -> TokenPair:
    # One conditional UPDATE: a concurrent request with the same token waits on the row lock
    # and then no longer matches revoked_at IS NULL.
    token_hash = hash_refresh_token(refresh_token)
    row = (
        await session.execute(
            update(models.RefreshToken)
            .where(
                models.RefreshToken.token_hash == token_hash,
                models.RefreshToken.revoked_at.is_(None),
                models.RefreshToken.expires_at > func.now(),
            )
            .values(revoked_at=func.now())
            .returning(models.RefreshToken.user_id, models.RefreshToken.family_id)
        )
    ).first()
    if row is None:
        # A revoked token coming back means it leaked: cut off whoever holds the newer one too.
        reused_family = await session.scalar(
            select(models.RefreshToken.family_id).where(
                models.RefreshToken.token_hash == token_hash,
                models.RefreshToken.revoked_at.is_not(None),
            )
        )
        if reused_family is not None:
            await _revoke_family(session, family_id=reused_family)
            raise RefreshTokenReusedError("refresh_token_reused", "Refresh token reuse detected")
        raise AuthenticationError("invalid_refresh_token", "Invalid refresh token")

    new_token = _issue_refresh_token(session, user_id=row.user_id, family_id=row.family_id)
    return TokenPair(access_token=create_access_token(row.user_id), refresh_token=new_token)


async def _revoke_family(session: AsyncSession, *, family_id: uuid.UUID) -> None:
    await session.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.family_id == family_id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )


def _issue_refresh_token(session: AsyncSession, *, user_id: int, family_id: uuid.UUID) -> str:
    raw = generate_refresh_token()
    session.add(
        models.RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return raw
