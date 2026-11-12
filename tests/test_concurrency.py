import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app import models
from tests import constants

pytestmark = pytest.mark.concurrency

# The rows here are really committed, so they need an address that is easy to sweep up.
RACE_DOMAIN = "race.example.com"


@pytest_asyncio.fixture
async def race_cleanup(engine):
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                delete(models.User).where(models.User.email.like(f"%@{RACE_DOMAIN}"))
            )


async def test_parallel_registrations_create_one_user(engine, committing_client, race_cleanup):
    email = f"racer@{RACE_DOMAIN}"
    payloads = [constants.user_payload(username=f"racer{i}", email=email) for i in range(5)]

    responses = await asyncio.gather(
        *(committing_client.post(constants.REGISTER_URL, json=p) for p in payloads)
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"email_taken"}
    async with engine.connect() as conn:
        users = await conn.scalar(
            select(func.count()).select_from(models.User).where(models.User.email == email)
        )
    assert users == 1


async def test_parallel_refreshes_with_one_token_revoke_the_family(
    engine, committing_client, race_cleanup
):
    payload = constants.user_payload(username="refresher", email=f"refresher@{RACE_DOMAIN}")
    await committing_client.post(constants.REGISTER_URL, json=payload)
    login = await committing_client.post(
        constants.LOGIN_URL, data={"username": payload["email"], "password": payload["password"]}
    )
    refresh_token = login.json()["refresh_token"]

    responses = await asyncio.gather(
        *(
            committing_client.post(constants.REFRESH_URL, json={"refresh_token": refresh_token})
            for _ in range(2)
        )
    )

    by_status = {r.status_code: r for r in responses}
    assert sorted(by_status) == [200, 401]
    assert by_status[401].json()["code"] == "refresh_token_reused"
    # The winner's new token belongs to the revoked family as well. Known limitation: two tabs
    # refreshing at once log the user out; a short grace period for the old token would fix it.
    winner = by_status[200].json()["refresh_token"]
    retry = await committing_client.post(constants.REFRESH_URL, json={"refresh_token": winner})
    assert retry.status_code == 401
    async with engine.connect() as conn:
        live_tokens = await conn.scalar(
            select(func.count())
            .select_from(models.RefreshToken)
            .join(models.User, models.User.id == models.RefreshToken.user_id)
            .where(models.User.email == payload["email"], models.RefreshToken.revoked_at.is_(None))
        )
    assert live_tokens == 0
