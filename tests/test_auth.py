import jwt
import pytest
from sqlalchemy import select

from app import models, schemas
from app.core.config import settings
from app.core.security import MAX_PASSWORD_BYTES, create_access_token
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
    assert payload["user_id"] == test_users[0].id


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
    token = create_access_token(data={"user_id": deleted_user.id})
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
