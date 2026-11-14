from fastapi import APIRouter, Depends, status

from .. import models, oauth2, schemas
from ..core.database import DbSession
from ..services import goals as goals_service

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.GoalOut)
async def create_goal(
    new_goal: schemas.GoalCreate,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return await goals_service.create_goal(
        db,
        owner_id=current_user.id,
        title=new_goal.title,
        description=new_goal.description,
        visibility=new_goal.visibility,
    )
