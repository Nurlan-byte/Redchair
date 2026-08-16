import jwt
import pytest
from sqlalchemy import select

from app import models, schemas
from app.core.config import settings


async def test_login_token(client, test_users):
    res = await client.post(
        f"{settings.api_v1_prefix}/login",
        data={"username": "aspas@gmail.com", "password": settings.TEST_PASSWORD},
    )
    assert res.status_code == 200
    token = schemas.Token(**res.json())
    assert token.token_type == "bearer"


async def test_token_user_id(client, test_users):
    res = await client.post(
        f"{settings.api_v1_prefix}/login",
        data={"username": "aspas@gmail.com", "password": settings.TEST_PASSWORD},
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
    res = await client.post(
        f"{settings.api_v1_prefix}/login", data={"username": email, "password": password}
    )
    assert res.status_code == status_code


NEW_USER = {
    "username": "Ahmed",
    "email": "Ahmed@gmail.com",
    "password": "Password12345",
    "confirm_password": "Password12345",
}


async def test_register_returns_created_user(client):
    res = await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)

    assert res.status_code == 201
    user = schemas.UserOut(**res.json())
    assert user.username == "Ahmed"
    assert user.email == "Ahmed@gmail.com"
    assert user.id > 0


async def test_register_does_not_leak_password(client):
    res = await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)

    res = res.json()
    assert "password" not in res
    assert "confirm_password" not in res
    assert "password_hash" not in res


async def test_register_creates_diary(client, session):
    res = await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)

    diary = await session.scalar(
        select(models.Diary).where(models.Diary.user_id == res.json()["id"])
    )
    assert diary is not None
    assert diary.is_public is True


async def test_registered_user_can_login(client):
    await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)

    res = await client.post(
        f"{settings.api_v1_prefix}/login",
        data={"username": NEW_USER["email"], "password": NEW_USER["password"]},
    )
    assert res.status_code == 200


async def test_register_duplicates(client, session):
    await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)
    res = await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)
    assert res.status_code == 409


async def test_register_rolls_back_user_if_diary_crashes(client, session, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("diary creation failed")

    monkeypatch.setattr("app.routers.auth.models.Diary", boom)
    with pytest.raises(RuntimeError):
        await client.post(f"{settings.api_v1_prefix}/register", json=NEW_USER)

    user = await session.scalar(
        select(models.User).where(models.User.username == NEW_USER["username"])
    )
    assert user is None
