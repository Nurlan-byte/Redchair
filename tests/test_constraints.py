import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app import models
from tests import constants


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(error.orig.__cause__, "constraint_name", None)


async def test_users_email_unique_constraint(session, test_users):
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(
                models.User(
                    username="newcomer",
                    email=test_users[0].email,
                    password_hash=constants.TEST_PASSWORD_HASH,
                )
            )
            await session.flush()

    assert _constraint_name(exc.value) == "uq_users_email"


async def test_users_username_unique_constraint(session, test_users):
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(
                models.User(
                    username=test_users[0].username,
                    email="newcomer@gmail.com",
                    password_hash=constants.TEST_PASSWORD_HASH,
                )
            )
            await session.flush()

    assert _constraint_name(exc.value) == "uq_users_username"


def _refresh_token(user_id: int, token_hash: str) -> models.RefreshToken:
    return models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )


async def test_refresh_tokens_token_hash_unique_constraint(session, test_users):
    token_hash = "a" * 64
    session.add(_refresh_token(test_users[0].id, token_hash))
    await session.flush()

    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(_refresh_token(test_users[1].id, token_hash))
            await session.flush()

    assert _constraint_name(exc.value) == "uq_refresh_tokens_token_hash"


async def test_deleting_user_cascades_to_refresh_tokens(session, test_users):
    user_id = test_users[0].id
    session.add(_refresh_token(user_id, "b" * 64))
    await session.flush()

    await session.execute(delete(models.User).where(models.User.id == user_id))

    remaining = await session.scalar(
        select(func.count())
        .select_from(models.RefreshToken)
        .where(models.RefreshToken.user_id == user_id)
    )
    assert remaining == 0


async def _goal(session, user: models.User) -> models.Goal:
    diary_id = await session.scalar(select(models.Diary.id).where(models.Diary.user_id == user.id))
    goal = models.Goal(diary_id=diary_id, title="Run every day")
    session.add(goal)
    await session.flush()
    return goal


async def test_goal_statistics_goal_id_unique_constraint(session, test_users):
    goal = await _goal(session, test_users[0])
    session.add(models.GoalStatistic(goal_id=goal.id))
    await session.flush()

    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(models.GoalStatistic(goal_id=goal.id))
            await session.flush()

    assert _constraint_name(exc.value) == "uq_goal_statistics_goal_id"


@pytest.mark.parametrize(
    ("current_streak", "longest_streak", "constraint"),
    [
        (-1, 0, "ck_goal_statistics_current_streak_non_negative"),
        (3, 2, "ck_goal_statistics_longest_streak_gte_current"),
    ],
)
async def test_goal_statistics_check_constraints(
    session, test_users, current_streak, longest_streak, constraint
):
    goal = await _goal(session, test_users[0])

    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(
                models.GoalStatistic(
                    goal_id=goal.id,
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                )
            )
            await session.flush()

    assert _constraint_name(exc.value) == constraint


ENTRY_DATE = date(2026, 9, 13)


def _entry(goal_id: int, **fields) -> models.DailyEntry:
    return models.DailyEntry(goal_id=goal_id, content="Ran 5 km", entry_date=ENTRY_DATE, **fields)


async def test_daily_entries_one_live_entry_per_goal_per_day(session, test_users):
    goal = await _goal(session, test_users[0])
    session.add(_entry(goal.id))
    await session.flush()

    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(_entry(goal.id))
            await session.flush()

    assert _constraint_name(exc.value) == "uq_daily_entries_goal_id_entry_date"


async def test_daily_entries_soft_deleted_entry_frees_its_day(session, test_users):
    goal = await _goal(session, test_users[0])
    session.add(_entry(goal.id, deleted_at=datetime.now(UTC)))
    await session.flush()

    session.add(_entry(goal.id))
    await session.flush()

    entries = await session.scalar(
        select(func.count())
        .select_from(models.DailyEntry)
        .where(models.DailyEntry.goal_id == goal.id, models.DailyEntry.entry_date == ENTRY_DATE)
    )
    assert entries == 2


async def test_daily_entries_visibility_check_constraint(session, test_users):
    goal = await _goal(session, test_users[0])

    # A plain string bypasses the Enum on the Python side and reaches the CHECK.
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(_entry(goal.id, visibility="FRIENDS"))
            await session.flush()

    assert _constraint_name(exc.value) == "ck_daily_entries_visibility"
