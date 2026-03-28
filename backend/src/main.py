# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from infrastructure.persistence.database import create_all_tables
from infrastructure.vector_store.chroma_client import get_chroma
from interfaces.api.v1 import auth, sources, articles, feed, criteria, tasks, health


settings = get_settings()
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    await get_chroma()          # ініціалізуємо з'єднання з Chroma
    yield


app = FastAPI(
    title=settings.app.name if hasattr(settings, "app") else "News Parser",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(health.router,   prefix=PREFIX)
app.include_router(auth.router,     prefix=PREFIX)
app.include_router(sources.router,  prefix=PREFIX)
app.include_router(articles.router, prefix=PREFIX)
app.include_router(feed.router,     prefix=PREFIX)
app.include_router(criteria.router, prefix=PREFIX)
app.include_router(tasks.router,    prefix=PREFIX)