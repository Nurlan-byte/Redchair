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
