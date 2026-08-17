import pytest

from app import schemas
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
    page = schemas.PaginatedResponse[schemas.UserOut](**res.json())
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
    page = schemas.PaginatedResponse[schemas.UserOut](**res.json())
    assert len(page.items) == expected_count


@pytest.mark.parametrize("query", ["aspas", "ASPAS", "Aspas"])
async def test_search_is_case_insensitive(authorized_client, test_users, query):
    res = await authorized_client.get(f"{constants.URL}/users", params={"username": query})

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.UserOut](**res.json())
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
    page = schemas.PaginatedResponse[schemas.UserOut](**res.json())
    assert page.has_more is expected_has_more


@pytest.mark.parametrize(
    "searched_username, username, email", [("aspas", "aspas", "aspas@gmail.com")]
)
async def test_happy_path_get_one_user(
    authorized_client, test_users, searched_username, username, email
):
    res = await authorized_client.get(f"{constants.URL}/users/{username}")
    user = schemas.UserOut(**res.json())
    assert res.status_code == 200
    assert user.username == "aspas"
    assert user.email == "aspas@gmail.com"


async def test_user_not_found(authorized_client, test_users):
    res = await authorized_client.get(f"{constants.URL}/users/not_exist")
    assert res.status_code == 404
