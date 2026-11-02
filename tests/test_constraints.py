import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app import models
from tests import constants


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(error.orig.__cause__, "constraint_name", None)


async def test_users_email_unique_constraint(session, test_users):
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(
                models.User(
                    username="newcomer",
                    email=test_users[0].email,
                    password_hash=constants.TEST_PASSWORD_HASH,
                )
            )
            await session.flush()

    assert _constraint_name(exc.value) == "uq_users_email"


async def test_users_username_unique_constraint(session, test_users):
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(
                models.User(
                    username=test_users[0].username,
                    email="newcomer@gmail.com",
                    password_hash=constants.TEST_PASSWORD_HASH,
                )
            )
            await session.flush()

    assert _constraint_name(exc.value) == "uq_users_username"


def _refresh_token(user_id: int, token_hash: str) -> models.RefreshToken:
    return models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )


async def test_refresh_tokens_token_hash_unique_constraint(session, test_users):
    token_hash = "a" * 64
    session.add(_refresh_token(test_users[0].id, token_hash))
    await session.flush()

    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(_refresh_token(test_users[1].id, token_hash))
            await session.flush()

    assert _constraint_name(exc.value) == "uq_refresh_tokens_token_hash"


async def test_deleting_user_cascades_to_refresh_tokens(session, test_users):
    user_id = test_users[0].id
    session.add(_refresh_token(user_id, "b" * 64))
    await session.flush()

    await session.execute(delete(models.User).where(models.User.id == user_id))

    remaining = await session.scalar(
        select(func.count())
        .select_from(models.RefreshToken)
        .where(models.RefreshToken.user_id == user_id)
    )
    assert remaining == 0
