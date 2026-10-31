import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app import models

from .core.config import settings
from .core.database import DbSession
from .exceptions import AuthenticationError

# auto_error=False: otherwise FastAPI answers a missing token itself, bypassing AppError.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


CREDENTIAL_ERRORS = (jwt.PyJWTError, KeyError, TypeError, ValueError)


async def get_current_user(
    db: DbSession, token: str | None = Depends(oauth2_scheme)
) -> models.User:
    if token is None:
        raise AuthenticationError("not_authenticated", "Not authenticated")

    invalid_token = AuthenticationError("invalid_token", "Could not validate credentials")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = int(payload["user_id"])
    except CREDENTIAL_ERRORS:
        raise invalid_token from None

    user = await db.get(models.User, user_id)
    if user is None or user.deleted_at is not None:
        raise invalid_token
    return user
