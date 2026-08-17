from app.core.config import settings
from app.utils import hash_password

TEST_PASSWORD = "Password12345"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)
URL = f"{settings.api_v1_prefix}"


def user_payload(**overrides):
    return {
        "username": "Ahmed",
        "email": "ahmed@gmail.com",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    } | overrides
