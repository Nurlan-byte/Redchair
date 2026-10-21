from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# bcrypt 5 raises ValueError on longer input instead of truncating it.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(raw, password_hash.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
