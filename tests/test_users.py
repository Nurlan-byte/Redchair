import pytest

from app import schemas
from app.core.security import create_access_token
from tests import constants


@pytest.mark.parametrize(
    "limit, offset, expected_count",
    [
        (None, None, 10),
        (5, None, 5),
        (3, 0, 3),
        (None, 8, 2),
    ],
)
async def test_pagination_respects_limit_and_offset(
    authorized_client, test_users, limit, offset, expected_count
):
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset

    res = await authorized_client.get(f"{constants.URL}/users", params=params)

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert len(page.items) == expected_count


@pytest.mark.parametrize(
    "query, expected_count",
    [
        ("aspas", 1),
        ("not_exist", 0),
    ],
)
async def test_search_by_username(authorized_client, test_users, query, expected_count):
    res = await authorized_client.get(f"{constants.URL}/users", params={"username": query})

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert len(page.items) == expected_count


@pytest.mark.parametrize("query", ["_", "%"])
async def test_search_escapes_like_wildcards(authorized_client, test_users, query):
    assert not any(query in user.username for user in test_users)

    res = await authorized_client.get(f"{constants.URL}/users", params={"username": query})

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert page.items == []


@pytest.mark.parametrize("query", ["aspas", "ASPAS", "Aspas"])
async def test_search_is_case_insensitive(authorized_client, test_users, query):
    res = await authorized_client.get(f"{constants.URL}/users", params={"username": query})

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert len(page.items) == 1
    assert page.items[0].username == "aspas"


@pytest.mark.parametrize(
    "limit, expected_has_more",
    [
        (5, True),
        (30, False),
    ],
)
async def test_has_more_reflects_remaining_items(
    authorized_client, test_users, limit, expected_has_more
):
    res = await authorized_client.get(f"{constants.URL}/users", params={"limit": limit})

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert page.has_more is expected_has_more


@pytest.mark.parametrize(
    "searched_username, username, email", [("aspas", "aspas", "aspas@gmail.com")]
)
async def test_happy_path_get_one_user(
    authorized_client, test_users, searched_username, username, email
):
    res = await authorized_client.get(f"{constants.URL}/users/{searched_username}")
    assert res.status_code == 200
    user = schemas.UserPublic(**res.json())
    assert user.username == username
    assert email not in res.text


async def test_user_not_found(authorized_client, test_users):
    res = await authorized_client.get(f"{constants.URL}/users/not_exist")
    assert res.status_code == 404
    assert res.json()["code"] == "user_not_found"


async def test_users_list_excludes_deleted_user(authorized_client, test_users, deleted_user):
    res = await authorized_client.get(f"{constants.URL}/users")

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserPublic](**res.json())
    assert len(page.items) == len(test_users) - 1
    assert deleted_user.id not in {user.id for user in page.items}


async def test_get_deleted_user_returns_404(authorized_client, deleted_user):
    res = await authorized_client.get(f"{constants.URL}/users/{deleted_user.username}")

    assert res.status_code == 404
    assert res.json()["code"] == "user_not_found"


async def test_users_requires_auth(client, test_users):
    res = await client.get(f"{constants.URL}/users")

    assert res.status_code == 401
    assert res.json()["code"] == "not_authenticated"
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_users_rejects_malformed_token(client, test_users):
    client.headers["Authorization"] = "Bearer not-a-jwt"

    res = await client.get(f"{constants.URL}/users")

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_token"


async def test_users_rejects_token_of_missing_user(client, test_users):
    missing_id = max(user.id for user in test_users) + 1
    client.headers["Authorization"] = f"Bearer {create_access_token(data={'user_id': missing_id})}"

    res = await client.get(f"{constants.URL}/users")

    assert res.status_code == 401
    assert res.json()["code"] == "invalid_token"


async def test_users_list_hides_email(authorized_client, test_users):
    res = await authorized_client.get(f"{constants.URL}/users")

    assert res.status_code == 200
    assert all("email" not in item for item in res.json()["items"])


async def test_me_returns_current_user_email(authorized_client, test_users):
    res = await authorized_client.get(f"{constants.URL}/users/me")

    assert res.status_code == 200
    me = schemas.UserPrivate(**res.json())
    assert me.id == test_users[0].id
    assert me.email == test_users[0].email


async def test_me_requires_auth(client, test_users):
    res = await client.get(f"{constants.URL}/users/me")

    assert res.status_code == 401
    assert res.json()["code"] == "not_authenticated"
