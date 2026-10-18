from fastapi import APIRouter, Depends, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..core import database
from ..services import auth as auth_service

router = APIRouter(tags=["Authentication"])


@router.post("/login")
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db),
):
    access_token = await auth_service.login(
        db, email=user_credentials.username, password=user_credentials.password
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
async def create_user(new_user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    return await auth_service.register_user(
        db,
        username=new_user.username,
        email=new_user.email,
        password=new_user.password,
    )
