from collections.abc import Sequence

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.exceptions import DomainValidationError, NotFoundError
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


async def _goal_tasks(session: AsyncSession, goal_id: int) -> Sequence[models.Task]:
    res = await session.scalars(
        select(models.Task)
        .where(models.Task.goal_id == goal_id)
        .order_by(models.Task.position, models.Task.id)
        .execution_options(populate_existing=True)
    )
    return res.all()


async def _get_task(
    session: AsyncSession, *, owner_id: int, goal_id: int, task_id: int
) -> models.Task:
    await goals_service.get_goal(session, owner_id=owner_id, goal_id=goal_id)
    task = await session.scalar(
        select(models.Task).where(models.Task.id == task_id, models.Task.goal_id == goal_id)
    )
    if task is None:
        raise NotFoundError("task_not_found", f"Task with id: {task_id} does not exist")
    return task


async def list_tasks(
    session: AsyncSession, *, owner_id: int, goal_id: int
) -> Sequence[models.Task]:
    await goals_service.get_goal(session, owner_id=owner_id, goal_id=goal_id)
    return await _goal_tasks(session, goal_id)


async def update_task(
    session: AsyncSession,
    *,
    owner_id: int,
    goal_id: int,
    task_id: int,
    title: str | None = None,
    is_done: bool | None = None,
) -> models.Task:
    task = await _get_task(session, owner_id=owner_id, goal_id=goal_id, task_id=task_id)
    if title is not None:
        task.title = title
    if is_done is not None:
        task.is_done = is_done
    await session.flush()
    return task


async def reorder_tasks(
    session: AsyncSession, *, owner_id: int, goal_id: int, task_ids: list[int]
) -> Sequence[models.Task]:
    await goals_service.get_goal(session, owner_id=owner_id, goal_id=goal_id)
    current = await session.scalars(select(models.Task.id).where(models.Task.goal_id == goal_id))
    if sorted(task_ids) != sorted(current.all()):
        raise DomainValidationError(
            "task_order_mismatch", "task_ids must list every task of the goal exactly once"
        )
    if task_ids:
        await session.execute(
            update(models.Task)
            .where(models.Task.goal_id == goal_id)
            .values(
                position=case(
                    {task_id: position for position, task_id in enumerate(task_ids)},
                    value=models.Task.id,
                )
            )
        )
    return await _goal_tasks(session, goal_id)


async def delete_task(session: AsyncSession, *, owner_id: int, goal_id: int, task_id: int) -> None:
    task = await _get_task(session, owner_id=owner_id, goal_id=goal_id, task_id=task_id)
    await session.delete(task)
    await session.flush()
