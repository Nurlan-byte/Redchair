from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app import models
from app.exceptions import NotFoundError


def _own_goals(owner_id: int) -> Select[tuple[models.Goal]]:
    return (
        select(models.Goal)
        .join(models.Diary, models.Diary.id == models.Goal.diary_id)
        .where(models.Diary.user_id == owner_id, models.Goal.deleted_at.is_(None))
        # Every goal has its statistic, so an inner join keeps it one query.
        .options(joinedload(models.Goal.statistic, innerjoin=True))
    )


async def create_goal(
    session: AsyncSession,
    *,
    owner_id: int,
    title: str,
    description: str | None,
    visibility: models.Visibility,
) -> models.Goal:
    diary_id = (
        await session.execute(select(models.Diary.id).where(models.Diary.user_id == owner_id))
    ).scalar_one()
    goal = models.Goal(
        diary_id=diary_id,
        title=title,
        description=description,
        visibility=visibility,
        statistic=models.GoalStatistic(),
    )
    session.add(goal)
    await session.flush()
    return goal


async def list_goals(
    session: AsyncSession, *, owner_id: int, limit: int, offset: int
) -> tuple[Sequence[models.Goal], bool]:
    res = await session.scalars(
        _own_goals(owner_id)
        .order_by(models.Goal.created_at.desc(), models.Goal.id.desc())
        .limit(limit + 1)
        .offset(offset)
    )
    goals = res.all()
    return goals[:limit], len(goals) > limit


async def get_goal(session: AsyncSession, *, owner_id: int, goal_id: int) -> models.Goal:
    # Someone else's goal is indistinguishable from a missing one.
    goal = await session.scalar(_own_goals(owner_id).where(models.Goal.id == goal_id))
    if goal is None:
        raise NotFoundError("goal_not_found", f"Goal with id: {goal_id} does not exist")
    return goal
