from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .core.config import settings
from .core.database import engine
from .exceptions import AppError
from .routers import auth, user


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(user.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    return {"message": "Hello, World!"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "detail": error.message or error.code},
        headers=headers,
    )