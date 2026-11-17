import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import models, schemas
from tests import constants


async def test_create_goal(authorized_client, session, test_users):
    payload = constants.goal_payload()

    res = await authorized_client.post(constants.GOALS_URL, json=payload)

    assert res.status_code == 201
    goal = schemas.GoalOut(**res.json())
    assert goal.title == payload["title"]
    assert goal.description == payload["description"]
    assert goal.visibility == payload["visibility"]
    owner_id = await session.scalar(
        select(models.Diary.user_id)
        .join(models.Goal, models.Goal.diary_id == models.Diary.id)
        .where(models.Goal.id == goal.id)
    )
    assert owner_id == test_users[0].id


async def test_create_goal_starts_with_empty_statistic(authorized_client, session):
    res = await authorized_client.post(constants.GOALS_URL, json=constants.goal_payload())

    statistic = schemas.GoalOut(**res.json()).statistic
    assert (statistic.current_streak, statistic.longest_streak) == (0, 0)
    assert statistic.last_entry_date is None
    stored = await session.scalar(
        select(models.GoalStatistic).where(models.GoalStatistic.goal_id == res.json()["id"])
    )
    assert stored is not None


async def test_goal_rolls_back_if_statistic_fails(authorized_client, session, monkeypatch):
    statistic_cls = models.GoalStatistic

    def broken_statistic(**kwargs):
        # Fails at flush, after the goal row has already been sent in the same flush.
        return statistic_cls(current_streak=-1)

    monkeypatch.setattr("app.services.goals.models.GoalStatistic", broken_statistic)
    with pytest.raises(IntegrityError):
        await authorized_client.post(constants.GOALS_URL, json=constants.goal_payload())

    goals = await session.scalar(select(func.count()).select_from(models.Goal))
    assert goals == 0


@pytest.mark.parametrize("title", ["   ", "x" * 201], ids=["blank", "too_long"])
async def test_create_goal_rejects_invalid_title(authorized_client, title):
    res = await authorized_client.post(
        constants.GOALS_URL, json=constants.goal_payload(title=title)
    )

    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "title"]


async def test_create_goal_requires_auth(client):
    res = await client.post(constants.GOALS_URL, json=constants.goal_payload())

    assert res.status_code == 401


async def test_list_goals_returns_own_newest_first(
    authorized_client, session, make_goals, test_users
):
    own = await make_goals(test_users[0], 3)
    await make_goals(test_users[1], 2)
    own[1].deleted_at = func.now()
    await session.flush()

    res = await authorized_client.get(constants.GOALS_URL)

    assert res.status_code == 200
    page = schemas.PaginatedResponse[schemas.GoalOut](**res.json())
    assert [goal.id for goal in page.items] == [own[2].id, own[0].id]
    assert page.has_more is False


async def test_get_own_goal(authorized_client, make_goals, test_users):
    [goal] = await make_goals(test_users[0], 1)

    res = await authorized_client.get(f"{constants.GOALS_URL}/{goal.id}")

    assert res.status_code == 200
    assert schemas.GoalOut(**res.json()).title == goal.title


async def test_foreign_goal_looks_missing(authorized_client, make_goals, test_users):
    [foreign] = await make_goals(test_users[1], 1)

    res = await authorized_client.get(f"{constants.GOALS_URL}/{foreign.id}")
    missing = await authorized_client.get(f"{constants.GOALS_URL}/{foreign.id + 1}")

    assert res.status_code == missing.status_code == 404
    assert res.json()["code"] == missing.json()["code"] == "goal_not_found"


async def test_list_goals_query_count_does_not_grow(
    authorized_client, make_goals, test_users, query_counter
):
    await make_goals(test_users[0], 1)
    query_counter.clear()
    await authorized_client.get(constants.GOALS_URL)
    one_goal = len(query_counter)

    await make_goals(test_users[0], 19)
    query_counter.clear()
    res = await authorized_client.get(constants.GOALS_URL)

    assert len(res.json()["items"]) == 20
    assert 0 < len(query_counter) == one_goal


async def test_update_goal_title(authorized_client, make_goals, test_users):
    [goal] = await make_goals(test_users[0], 1)

    res = await authorized_client.patch(
        f"{constants.GOALS_URL}/{goal.id}", json={"title": "Read 30 pages a day"}
    )

    assert res.status_code == 200
    assert schemas.GoalOut(**res.json()).title == "Read 30 pages a day"


async def test_update_goal_clears_description_with_null(
    authorized_client, session, make_goals, test_users
):
    [goal] = await make_goals(test_users[0], 1)
    goal.description = "Any book counts"
    await session.flush()

    res = await authorized_client.patch(
        f"{constants.GOALS_URL}/{goal.id}", json={"description": None}
    )

    assert res.status_code == 200
    assert res.json()["description"] is None


async def test_update_goal_keeps_omitted_fields(authorized_client, session, make_goals, test_users):
    [goal] = await make_goals(test_users[0], 1)
    goal.description = "Any book counts"
    await session.flush()

    res = await authorized_client.patch(
        f"{constants.GOALS_URL}/{goal.id}", json={"visibility": "PRIVATE"}
    )

    updated = schemas.GoalOut(**res.json())
    assert updated.visibility == models.Visibility.PRIVATE
    assert (updated.title, updated.description) == (goal.title, goal.description)


async def test_update_foreign_goal_returns_404(authorized_client, make_goals, test_users):
    [foreign] = await make_goals(test_users[1], 1)

    res = await authorized_client.patch(
        f"{constants.GOALS_URL}/{foreign.id}", json={"title": "Not mine"}
    )

    assert res.status_code == 404
    assert foreign.title == "Goal 0"


async def test_delete_goal(authorized_client, make_goals, test_users):
    [goal] = await make_goals(test_users[0], 1)

    res = await authorized_client.delete(f"{constants.GOALS_URL}/{goal.id}")
    after = await authorized_client.get(f"{constants.GOALS_URL}/{goal.id}")

    assert res.status_code == 204
    assert after.status_code == 404


async def test_deleted_goal_not_listed(authorized_client, make_goals, test_users):
    kept, deleted = await make_goals(test_users[0], 2)
    await authorized_client.delete(f"{constants.GOALS_URL}/{deleted.id}")

    res = await authorized_client.get(constants.GOALS_URL)

    assert [goal["id"] for goal in res.json()["items"]] == [kept.id]
