from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas, utils
from ..core.database import get_db

router = APIRouter(prefix="/users", tags=["Users"])


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


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
async def create_user(new_user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.email == new_user.email))
    email_exist = res.scalar_one_or_none()
    if email_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )
    res = await db.execute(select(models.User).where(models.User.username == new_user.username))
    username_exist = res.scalar_one_or_none()
    if username_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    user = models.User(
        username=new_user.username,
        email=new_user.email,
        password_hash=utils.hash_password(new_user.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
