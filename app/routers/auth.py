from fastapi import APIRouter, Depends, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm

from .. import schemas
from ..core.database import DbSession
from ..services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=schemas.Token)
async def login(
    db: DbSession,
    user_credentials: OAuth2PasswordRequestForm = Depends(),
):
    pair = await auth_service.login(
        db, email=user_credentials.username, password=user_credentials.password
    )
    return schemas.Token(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=schemas.Token)
async def refresh(body: schemas.RefreshRequest, db: DbSession):
    pair = await auth_service.refresh(db, refresh_token=body.refresh_token)
    return schemas.Token(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: schemas.RefreshRequest, db: DbSession) -> None:
    # Same answer for unknown, revoked and live tokens: logout reveals nothing.
    await auth_service.logout(db, refresh_token=body.refresh_token)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserPrivate)
async def create_user(new_user: schemas.UserCreate, db: DbSession):
    return await auth_service.register_user(
        db,
        username=new_user.username,
        email=new_user.email,
        password=new_user.password,
        timezone=new_user.timezone,
    )
