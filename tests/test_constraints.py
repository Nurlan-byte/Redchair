import pytest
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
