from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.config import settings
from .core.database import engine
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
