from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


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
