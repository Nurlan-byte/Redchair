import json

import pytest

from app.exceptions import AppError, AuthenticationError, ConflictError, NotFoundError
from app.main import app_error_handler


@pytest.mark.parametrize(
    "error, status_code",
    [
        (NotFoundError("user_not_found"), 404),
        (ConflictError("email_taken", "Email already registered"), 409),
        (AuthenticationError("invalid_credentials"), 401),
    ],
)
async def test_app_error_maps_to_status_and_body(error: AppError, status_code: int):
    res = await app_error_handler(None, error)

    assert res.status_code == status_code
    body = json.loads(res.body)
    assert body["code"] == error.code
    assert body["detail"] == (error.message or error.code)


async def test_authentication_error_sets_www_authenticate():
    res = await app_error_handler(None, AuthenticationError("invalid_credentials"))
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_non_auth_error_has_no_www_authenticate():
    res = await app_error_handler(None, ConflictError("email_taken"))
    assert "WWW-Authenticate" not in res.headers
