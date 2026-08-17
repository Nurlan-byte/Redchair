from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, oauth2, schemas
from ..core.database import get_db

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(oauth2.get_current_user)])


@router.get("", response_model=schemas.PaginatedResponse[schemas.UserOut])
async def all_users(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    username: str | None = Query(None),
):
    stmt = select(models.User)

    if username:
        stmt = stmt.where(models.User.username.ilike(f"%{username}%"))
    res = await db.scalars(stmt.order_by(models.User.id.desc()).limit(limit + 1).offset(offset))
    users = res.all()
    has_more = len(users) > limit
    return schemas.PaginatedResponse(
        items=users[:limit], limit=limit, offset=offset, has_more=has_more
    )


@router.get("/{username}", response_model=schemas.UserOut)
async def get_one_user(username: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.username == username))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with username: {username} does not exist",
        )
    return user
