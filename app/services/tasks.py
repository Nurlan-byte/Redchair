from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services import goals as goals_service


async def create_task(
    session: AsyncSession, *, owner_id: int, goal_id: int, title: str
) -> models.Task:
    await goals_service.get_goal(session, owner_id=owner_id, goal_id=goal_id)
    # Two concurrent appends may get the same position; reads break the tie by id.
    position = await session.scalar(
        select(func.coalesce(func.max(models.Task.position) + 1, 0)).where(
            models.Task.goal_id == goal_id
        )
    )
    task = models.Task(goal_id=goal_id, title=title, position=position)
    session.add(task)
    await session.flush()
    return task


async def list_tasks(
    session: AsyncSession, *, owner_id: int, goal_id: int
) -> Sequence[models.Task]:
    await goals_service.get_goal(session, owner_id=owner_id, goal_id=goal_id)
    res = await session.scalars(
        select(models.Task)
        .where(models.Task.goal_id == goal_id)
        .order_by(models.Task.position, models.Task.id)
    )
    return res.all()
