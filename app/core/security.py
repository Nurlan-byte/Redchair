import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# bcrypt 5 raises ValueError on longer input instead of truncating it.
MAX_PASSWORD_BYTES = 72
REFRESH_TOKEN_BYTES = 32


def hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(settings.bcrypt_rounds)).decode()


# bcrypt is pure CPU work that releases the GIL: in a thread it neither blocks the event loop
# nor waits for other checks.
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password_sync, password)


async def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    return await asyncio.to_thread(bcrypt.checkpw, raw, password_hash.encode())


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        # PyJWT 2.10+ rejects a non-string sub on decode.
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    # 256 random bits need no salt or slow hash, and a deterministic digest can be looked up.
    return hashlib.sha256(token.encode()).hexdigest()
