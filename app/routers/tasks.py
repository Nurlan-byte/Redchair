from fastapi import APIRouter, Depends, status

from .. import models, oauth2, schemas
from ..core.database import DbSession
from ..services import tasks as tasks_service

router = APIRouter(prefix="/goals/{goal_id}/tasks", tags=["Tasks"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.TaskOut)
async def create_task(
    goal_id: int,
    new_task: schemas.TaskCreate,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return await tasks_service.create_task(
        db, owner_id=current_user.id, goal_id=goal_id, title=new_task.title
    )


@router.get("", response_model=list[schemas.TaskOut])
async def list_tasks(
    goal_id: int,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return await tasks_service.list_tasks(db, owner_id=current_user.id, goal_id=goal_id)
