from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, oauth2, schemas, utils
from ..core import database

router = APIRouter(tags=["Authentication"])


@router.post("/login")
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db),
):
    res = await db.execute(
        select(models.User).where(models.User.email == user_credentials.username)
    )

    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not utils.verify(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
async def create_user(new_user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.User).where(models.User.email == new_user.email))
    email_exist = res.scalar_one_or_none()
    if email_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    res = await db.execute(select(models.User).where(models.User.username == new_user.username))
    username_exist = res.scalar_one_or_none()
    if username_exist:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )
    user = models.User(
        username=new_user.username,
        email=new_user.email,
        password_hash=utils.hash_password(new_user.password),
    )
    db.add(user)
    await db.flush()
    diary = models.Diary(user_id=user.id)
    db.add(diary)
    return user
