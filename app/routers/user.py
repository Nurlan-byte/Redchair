from fastapi import APIRouter, Depends, Query

from .. import models, oauth2, schemas
from ..core.database import DbSession
from ..services import users as users_service

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(oauth2.get_current_user)])


@router.get("", response_model=schemas.PaginatedResponse[schemas.UserPublic])
async def all_users(
    db: DbSession,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    username: str | None = Query(None),
):
    users, has_more = await users_service.list_users(
        db, limit=limit, offset=offset, username=username
    )
    return schemas.PaginatedResponse(items=users, limit=limit, offset=offset, has_more=has_more)


# Declared before /{username}, otherwise "me" is captured as a username.
@router.get("/me", response_model=schemas.UserPrivate)
async def get_me(current_user: models.User = Depends(oauth2.get_current_user)):
    return current_user


@router.get("/{username}", response_model=schemas.UserPublic)
async def get_one_user(username: str, db: DbSession):
    return await users_service.get_user_by_username(db, username=username)
