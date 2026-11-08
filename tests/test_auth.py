import hashlib
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select, update

from app import models, schemas
from app.core.config import settings
from app.core.security import MAX_PASSWORD_BYTES, create_access_token
from app.exceptions import ConflictError
from tests import constants


async def test_login_token(client, test_users):
    res = await client.post(
        constants.LOGIN_URL,
        data={"username": "aspas@gmail.com", "password": constants.TEST_PASSWORD},
    )
    assert res.status_code == 200
    token = schemas.Token(**res.json())
    assert token.token_type == "bearer"


async def test_token_user_id(client, test_users):
    res = await client.post(
        constants.LOGIN_URL,
        data={"username": "aspas@gmail.com", "password": constants.TEST_PASSWORD},
    )
    payload = jwt.decode(res.json()["access_token"], settings.secret_key, settings.algorithm)
    assert int(payload["sub"]) == test_users[0].id


async def _login(client, user: models.User) -> schemas.Token:
    res = await client.post(
        constants.LOGIN_URL,
        data={"username": user.email, "password": constants.TEST_PASSWORD},
    )
    assert res.status_code == 200
    return schemas.Token(**res.json())


async def _stored_refresh_tokens(session, user: models.User) -> list[models.RefreshToken]:
    res = await session.scalars(
        select(models.RefreshToken)
        .where(models.RefreshToken.user_id == user.id)
        .order_by(models.RefreshToken.id)
        # The request ran in this same session; reload what its UPDATE changed.
        .execution_options(populate_existing=True)
    )
    return list(res)


async def _refresh(client, refresh_token: str):
    return await client.post(constants.REFRESH_URL, json={"refresh_token": refresh_token})


async def test_login_returns_refresh_token(client, test_users):
    token = await _login(client, test_users[0])

    assert token.refresh_token
    assert token.refresh_token != token.access_token


async def test_login_stores_only_refresh_token_hash(client, session, test_users):
    token = await _login(client, test_users[0])

    stored = await _stored_refresh_tokens(session, test_users[0])
    assert [t.token_hash for t in stored] == [
        hashlib.sha256(token.refresh_token.encode()).hexdigest()
    ]
    raw_matches = await session.scalar(
        select(func.count())
        .select_from(models.RefreshToken)
        .where(models.RefreshToken.token_hash == token.refresh_token)
    )
    assert raw_matches == 0


async def test_login_refresh_token_expires_after_configured_days(client, session, test_users):
    await _login(client, test_users[0])

    [stored] = await _stored_refresh_tokens(session, test_users[0])
    expected = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    assert abs(stored.expires_at - expected) < timedelta(minutes=1)


async def test_refresh_rotates_token(client, session, test_users):
    old = await _login(client, test_users[0])

    res = await _refresh(client, old.refresh_token)

    assert res.status_code == 200
    new = schemas.Token(**res.json())
    assert new.refresh_token != old.refresh_token
    old_row, new_row = await _stored_refresh_tokens(session, test_users[0])
    assert old_row.token_hash == hashlib.sha256(old.refresh_token.encode()).hexdigest()
    assert old_row.revoked_at is not None
    assert new_row.revoked_at is None
    assert new_row.family_id == old_row.family_id


async def test_refreshed_access_token_works(client, test_users):
    old = await _login(client, test_users[0])
    new = schemas.Token(**(await _refresh(client, old.refresh_token)).json())

    res = await client.get(
        f"{constants.URL}/users/me", headers={"Authorization": f"Bearer {new.access_token}"}
    )

    assert res.status_code == 200
    assert res.json()["id"] == test_users[0].id


async def test_expired_refresh_returns_401(client, session, test_users):
    token = await _login(client, test_users[0])
    # now() is frozen at the start of the test transaction, so move the data instead.
    await session.execute(
        update(models.RefreshToken)
        .where(models.RefreshToken.user_id == test_users[0].id)
        .values(expires_at=datetime.now(UTC) - timedelta(days=1))
    )

    res = await _refresh(client, token.refresh_token)

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_refresh_token"


async def test_refresh_with_unknown_token_returns_401(client, test_users):
    res = await _refresh(client, "not-a-refresh-token")

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_refresh_token"


async def test_reused_refresh_token_revokes_family(client, session, test_users):
    first = await _login(client, test_users[0])
    second = schemas.Token(**(await _refresh(client, first.refresh_token)).json())

    reuse = await _refresh(client, first.refresh_token)

    assert reuse.status_code == 401
    assert reuse.json()["code"] == "refresh_token_reused"
    assert (await _refresh(client, second.refresh_token)).status_code == 401
    stored = await _stored_refresh_tokens(session, test_users[0])
    assert all(t.revoked_at is not None for t in stored)


async def _logout(client, refresh_token: str):
    return await client.post(constants.LOGOUT_URL, json={"refresh_token": refresh_token})


async def test_logout_revokes_family(client, session, test_users):
    first = await _login(client, test_users[0])
    second = schemas.Token(**(await _refresh(client, first.refresh_token)).json())

    res = await _logout(client, second.refresh_token)

    assert res.status_code == 204
    stored = await _stored_refresh_tokens(session, test_users[0])
    assert len(stored) == 2
    assert all(t.revoked_at is not None for t in stored)
    assert (await _refresh(client, second.refresh_token)).status_code == 401


async def test_logout_twice_returns_204(client, test_users):
    token = await _login(client, test_users[0])

    first = await _logout(client, token.refresh_token)
    second = await _logout(client, token.refresh_token)

    assert (first.status_code, second.status_code) == (204, 204)


async def test_access_token_survives_logout(client, test_users):
    # Known trade-off: access tokens are not checked against refresh families, so one stays
    # valid until it expires. Checking would cost a second query on every request.
    token = await _login(client, test_users[0])
    await _logout(client, token.refresh_token)

    res = await client.get(
        f"{constants.URL}/users/me", headers={"Authorization": f"Bearer {token.access_token}"}
    )

    assert res.status_code == 200


async def test_app_error_still_rolls_back_the_request(client, session, monkeypatch):
    def conflict(*args, **kwargs):
        raise ConflictError("diary_conflict")

    monkeypatch.setattr("app.services.auth.models.Diary", conflict)
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload())

    assert res.status_code == 409
    user = await session.scalar(
        select(models.User).where(models.User.username == constants.user_payload()["username"])
    )
    assert user is None


def test_access_token_sub_is_string_user_id():
    user_id = 42

    payload = jwt.decode(create_access_token(user_id), settings.secret_key, settings.algorithm)

    assert payload["sub"] == str(user_id)
    assert payload["iat"] <= payload["exp"]


def test_access_tokens_have_unique_jti():
    first = jwt.decode(create_access_token(1), settings.secret_key, settings.algorithm)
    second = jwt.decode(create_access_token(1), settings.secret_key, settings.algorithm)

    assert first["jti"] != second["jti"]


@pytest.mark.parametrize(
    "email, password, status_code",
    [
        ("pedri@gmail.com", "wrong_password", 401),
        ("wrong_email", "Password12345", 401),
        ("wrong_email", "wrong_password", 401),
        ("pedri@gmail.com", "", 422),
        (None, "Password12345", 422),
        ("pedri@gmail.com", None, 422),
    ],
)
async def test_incorrect_login(client, test_users, email, password, status_code):
    res = await client.post(constants.LOGIN_URL, data={"username": email, "password": password})
    assert res.status_code == status_code


async def test_login_of_deleted_user_returns_401(client, deleted_user):
    res = await client.post(
        constants.LOGIN_URL,
        data={"username": deleted_user.email, "password": constants.TEST_PASSWORD},
    )

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_credentials"


async def test_token_of_deleted_user_returns_401(client, deleted_user):
    token = create_access_token(deleted_user.id)
    client.headers["Authorization"] = f"Bearer {token}"

    res = await client.get(f"{constants.URL}/users/me")

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_token"


async def test_register_returns_created_user(client):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload())

    assert res.status_code == 201
    user = schemas.UserPrivate(**res.json())
    assert user.username == "Ahmed"
    assert user.email == "ahmed@gmail.com"
    assert user.id > 0


async def test_register_defaults_timezone_to_utc(client):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload())

    assert res.status_code == 201
    assert schemas.UserPrivate(**res.json()).timezone == "UTC"


async def test_register_accepts_valid_timezone(client):
    timezone = "Asia/Almaty"

    res = await client.post(constants.REGISTER_URL, json=constants.user_payload(timezone=timezone))

    assert res.status_code == 201
    assert schemas.UserPrivate(**res.json()).timezone == timezone


@pytest.mark.parametrize(
    "timezone", ["Mars/Olympus", "", "../etc/passwd"], ids=["unknown", "empty", "path"]
)
async def test_register_rejects_invalid_timezone(client, timezone):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload(timezone=timezone))

    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "timezone"]


async def test_register_does_not_leak_password(client):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload())

    res = res.json()
    assert "password" not in res
    assert "confirm_password" not in res
    assert "password_hash" not in res


async def test_register_creates_diary(client, session):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload())

    diary = await session.scalar(
        select(models.Diary).where(models.Diary.user_id == res.json()["id"])
    )
    assert diary is not None
    assert diary.is_public is True


async def test_registered_user_can_login(client):
    await client.post(constants.REGISTER_URL, json=constants.user_payload())

    res = await client.post(
        constants.LOGIN_URL,
        data={
            "username": constants.user_payload()["email"],
            "password": constants.user_payload()["password"],
        },
    )
    assert res.status_code == 200


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"username": "Ahmed2"}, "email_taken"),
        ({"email": "ahmed2@gmail.com"}, "username_taken"),
    ],
    ids=["email", "username"],
)
async def test_register_duplicate_returns_409_with_code(client, overrides, code):
    await client.post(constants.REGISTER_URL, json=constants.user_payload())

    res = await client.post(constants.REGISTER_URL, json=constants.user_payload(**overrides))

    assert res.status_code == 409
    assert res.json()["code"] == code


async def test_register_upper_case_email_then_login_lower_case(client):
    email = constants.user_payload()["email"]
    await client.post(constants.REGISTER_URL, json=constants.user_payload(email=email.upper()))

    res = await client.post(
        constants.LOGIN_URL,
        data={"username": email, "password": constants.TEST_PASSWORD},
    )

    assert res.status_code == 200


async def test_register_duplicate_email_in_other_case_returns_409(client):
    email = constants.user_payload()["email"]
    await client.post(constants.REGISTER_URL, json=constants.user_payload())

    res = await client.post(
        constants.REGISTER_URL,
        json=constants.user_payload(username="Ahmed2", email=email.upper()),
    )

    assert res.status_code == 409
    assert res.json()["code"] == "email_taken"


@pytest.mark.parametrize(
    "password",
    ["Aa1" + "a" * 70, "Ж" + "ж" * 35 + "1"],
    ids=["ascii-73", "cyrillic-37"],
)
async def test_register_rejects_long_password(client, password):
    assert len(password.encode()) > MAX_PASSWORD_BYTES

    res = await client.post(
        constants.REGISTER_URL,
        json=constants.user_payload(password=password, confirm_password=password),
    )

    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "password"]


async def test_login_with_long_password_returns_401(client, test_users):
    res = await client.post(
        constants.LOGIN_URL,
        data={"username": test_users[0].email, "password": "a" * (MAX_PASSWORD_BYTES + 1)},
    )

    assert res.status_code == 401


async def test_register_rejects_reserved_username(client):
    res = await client.post(constants.REGISTER_URL, json=constants.user_payload(username="me"))

    assert res.status_code == 422
    assert res.json()["code"] == "username_reserved"


async def test_register_rolls_back_user_if_diary_crashes(client, session, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("diary creation failed")

    monkeypatch.setattr("app.services.auth.models.Diary", boom)
    with pytest.raises(RuntimeError):
        await client.post(constants.REGISTER_URL, json=constants.user_payload())

    user = await session.scalar(
        select(models.User).where(models.User.username == constants.user_payload()["username"])
    )
    assert user is None
