# presentation/api/main.py
"""
Точка входу FastAPI.

Тут живуть:
- lifespan (startup/shutdown)
- підключення роутерів

Presentation може знати про application (use cases) та container.
НЕ імпортує напряму з БД або SQLAlchemy!
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from infrastructure.config.container import get_container
from infrastructure.persistence.database import create_all_tables
from infrastructure.task_queue.background_queue import register_task
from presentation.api.routes import sources, feed, auth

logger = logging.getLogger(__name__)


# ─── Реєстрація фонових задач ────────────────────────────────────────────────
# Тут infrastructure підключає конкретні задачі до черги.
# Application лише знає рядкові імена ("ingest_source").

@register_task("ingest_source")
async def _task_ingest_source(source_id: str) -> None:
    """Фонова задача парсингу одного джерела."""
    from uuid import UUID
    from infrastructure.fetchers.rss_fetcher import RssFetcher
    from infrastructure.persistence.repositories.source_repo import SourceRepository
    from infrastructure.persistence.repositories.raw_article_repo import RawArticleRepository
    from infrastructure.persistence.repositories.fetch_job_repo import FetchJobRepository
    from application.use_cases.ingest_source import IngestSourceUseCase

    container = get_container()
    async with container.make_session() as session:
        async with session.begin():
            result = await IngestSourceUseCase(
                source_repo=SourceRepository(session),
                raw_article_repo=RawArticleRepository(session),
                fetch_job_repo=FetchJobRepository(session),
                fetcher=RssFetcher(),
            ).execute(UUID(source_id))

    logger.info(
        "Ingest done: source=%s fetched=%d saved=%d skipped=%d error=%s",
        source_id, result.fetched, result.saved, result.skipped_duplicates, result.error,
    )


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Все що відбувається при старті та зупинці.
    Порядок: init DB → run startup use case → yield → cleanup.
    """
    logger.info("=== App startup ===")

    # 1. Створюємо таблиці (якщо не існують)
    await create_all_tables()
    logger.info("Database tables ready")

    # 2. Запускаємо startup use case через container
    container = get_container()
    from application.use_cases.startup import StartupUseCase
    from infrastructure.persistence.repositories.source_repo import SourceRepository

    async with container.make_session() as session:
        result = await StartupUseCase(
            source_repo=SourceRepository(session),
            task_queue=container.task_queue,
        ).execute()

    logger.info(
        "Startup complete: %d sources found, %d tasks enqueued",
        result.sources_found, result.tasks_enqueued,
    )

    yield  # ← тут FastAPI обробляє запити

    logger.info("=== App shutdown ===")


# ─── FastAPI app ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="News Parser API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(auth.router,    prefix="/api/v1/auth",    tags=["auth"])
    app.include_router(sources.router, prefix="/api/v1/sources", tags=["sources"])
    app.include_router(feed.router,    prefix="/api/v1/feed",    tags=["feed"])

    return app


app = create_app()