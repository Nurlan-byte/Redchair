from fastapi import APIRouter, Depends, Query, status

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


@router.get("", response_model=schemas.PaginatedResponse[schemas.GoalOut])
async def list_goals(
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    goals, has_more = await goals_service.list_goals(
        db, owner_id=current_user.id, limit=limit, offset=offset
    )
    return schemas.PaginatedResponse(items=goals, limit=limit, offset=offset, has_more=has_more)


@router.get("/{goal_id}", response_model=schemas.GoalOut)
async def get_goal(
    goal_id: int,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return await goals_service.get_goal(db, owner_id=current_user.id, goal_id=goal_id)


@router.patch("/{goal_id}", response_model=schemas.GoalOut)
async def update_goal(
    goal_id: int,
    changes: schemas.GoalUpdate,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return await goals_service.update_goal(
        db,
        owner_id=current_user.id,
        goal_id=goal_id,
        **changes.model_dump(exclude_unset=True),
    )


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    db: DbSession,
    current_user: models.User = Depends(oauth2.get_current_user),
) -> None:
    await goals_service.delete_goal(db, owner_id=current_user.id, goal_id=goal_id)
