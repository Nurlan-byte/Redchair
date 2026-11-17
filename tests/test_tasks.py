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
