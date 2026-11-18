import pytest
from sqlalchemy import func

from app import models, schemas
from tests import constants


async def test_tasks_are_appended_to_the_end(authorized_client, make_goals, test_users):
    [goal] = await make_goals(test_users[0])

    positions = []
    for title in ("Buy a book", "Read chapter 1", "Read chapter 2"):
        res = await authorized_client.post(constants.tasks_url(goal.id), json={"title": title})
        assert res.status_code == 201
        positions.append(schemas.TaskOut(**res.json()).position)

    assert positions == [0, 1, 2]


async def test_list_tasks_orders_by_position_then_id(
    authorized_client, session, make_goals, test_users
):
    [goal] = await make_goals(test_users[0])
    tasks = [
        models.Task(goal_id=goal.id, title="third", position=1),
        models.Task(goal_id=goal.id, title="first", position=0),
        # Same position as the one above: the tie is broken by id.
        models.Task(goal_id=goal.id, title="second", position=0),
    ]
    session.add_all(tasks)
    await session.flush()

    res = await authorized_client.get(constants.tasks_url(goal.id))

    assert res.status_code == 200
    assert [task["title"] for task in res.json()] == ["first", "second", "third"]


async def test_tasks_of_foreign_or_deleted_goal_return_404(
    authorized_client, session, make_goals, test_users
):
    [foreign] = await make_goals(test_users[1])
    [deleted] = await make_goals(test_users[0])
    deleted.deleted_at = func.now()
    await session.flush()

    for goal in (foreign, deleted):
        listed = await authorized_client.get(constants.tasks_url(goal.id))
        created = await authorized_client.post(
            constants.tasks_url(goal.id), json={"title": "Sneak in"}
        )
        assert listed.status_code == created.status_code == 404


async def _add_tasks(session, goal: models.Goal, count: int) -> list[models.Task]:
    tasks = [models.Task(goal_id=goal.id, title=f"Task {i}", position=i) for i in range(count)]
    session.add_all(tasks)
    await session.flush()
    return tasks


async def test_mark_task_done(authorized_client, session, make_goals, test_users):
    [goal] = await make_goals(test_users[0])
    [task] = await _add_tasks(session, goal, 1)

    res = await authorized_client.patch(
        f"{constants.tasks_url(goal.id)}/{task.id}", json={"is_done": True}
    )

    assert res.status_code == 200
    updated = schemas.TaskOut(**res.json())
    assert updated.is_done is True
    assert updated.title == task.title


async def test_reorder_tasks(authorized_client, session, make_goals, test_users):
    [goal] = await make_goals(test_users[0])
    first, second, third = await _add_tasks(session, goal, 3)
    new_order = [third.id, first.id, second.id]

    res = await authorized_client.put(
        f"{constants.tasks_url(goal.id)}/order", json={"task_ids": new_order}
    )

    assert res.status_code == 200
    assert [(task["id"], task["position"]) for task in res.json()] == [
        (third.id, 0),
        (first.id, 1),
        (second.id, 2),
    ]


@pytest.mark.parametrize("mismatch", ["missing", "foreign"])
async def test_reorder_rejects_mismatched_ids(
    authorized_client, session, make_goals, test_users, mismatch
):
    [goal] = await make_goals(test_users[0])
    [foreign_goal] = await make_goals(test_users[1])
    first, second = await _add_tasks(session, goal, 2)
    [foreign] = await _add_tasks(session, foreign_goal, 1)
    task_ids = [second.id] if mismatch == "missing" else [second.id, first.id, foreign.id]

    res = await authorized_client.put(
        f"{constants.tasks_url(goal.id)}/order", json={"task_ids": task_ids}
    )

    assert res.status_code == 422
    assert res.json()["code"] == "task_order_mismatch"


async def test_delete_task(authorized_client, session, make_goals, test_users):
    [goal] = await make_goals(test_users[0])
    kept, deleted = await _add_tasks(session, goal, 2)

    res = await authorized_client.delete(f"{constants.tasks_url(goal.id)}/{deleted.id}")
    remaining = await authorized_client.get(constants.tasks_url(goal.id))

    assert res.status_code == 204
    assert [task["id"] for task in remaining.json()] == [kept.id]
