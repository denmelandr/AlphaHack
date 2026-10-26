from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import applications, auth, policies, portfolio, products, tools
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схема приводится к последней версии миграциями Alembic, затем сид.
    command.upgrade(Config("alembic.ini"), "head")
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Умный кредитный кабинет — API",
    version="0.1.0",
    description="Цифровой кредитный конвейер для малого и микробизнеса.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(applications.router)
app.include_router(tools.router)
app.include_router(policies.router)
app.include_router(portfolio.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}
