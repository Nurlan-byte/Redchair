import jwt
import pytest

from app import schemas
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
