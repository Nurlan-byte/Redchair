from app.core.config import settings
from app.core.security import hash_password_sync

TEST_PASSWORD = "Password12345"
TEST_PASSWORD_HASH = hash_password_sync(TEST_PASSWORD)
URL = f"{settings.api_v1_prefix}"
LOGIN_URL = f"{URL}/auth/login"
REGISTER_URL = f"{URL}/auth/register"
REFRESH_URL = f"{URL}/auth/refresh"
LOGOUT_URL = f"{URL}/auth/logout"
GOALS_URL = f"{URL}/goals"


def tasks_url(goal_id: int) -> str:
    return f"{GOALS_URL}/{goal_id}/tasks"


def user_payload(**overrides):
    return {
        "username": "Ahmed",
        "email": "ahmed@gmail.com",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
    } | overrides


def goal_payload(**overrides):
    return {
        "title": "Read 20 pages a day",
        "description": "Any book counts",
        "visibility": "PRIVATE",
    } | overrides
