# presentation/api/main.py
"""
FastAPI точка входу.

Lifespan відповідає за:
  1. init_container()         — створення singleton залежностей
  2. register_all_tasks()     — реєстрація worker handlers
  3. create_all_tables()      — міграція БД (dev) або перевірка (prod)
  4. StartupUseCase.execute() — поставити всі активні джерела в чергу
  5. _start_scheduler()       — periodic re-scheduling (APScheduler)
  6. container.close()        — закрити з'єднання при shutdown

Порядок важливий:
  container → register_tasks → create_tables → startup_use_case → scheduler
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from src.config.logger import setup_logging
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

setup_logging()


logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. DI Container ──────────────────────────────────────────────────────
    logger.info("Starting up application...")
    from src.config.container import init_container
    container = init_container()
    await container.init_async()

    # ── 2. Task registry — handler функції реєструються після container ──────
    #    (handlers.py використовує get_container() всередині)
    from src.infrastructure.task_queue.registry import register_all_tasks
    register_all_tasks()

    # ── 3. БД ─────────────────────────────────────────────────────────────────
    from src.infrastructure.persistence.database import create_all_tables
    await create_all_tables()
    logger.info("Database ready")

    # ── 4. Startup use case — запускаємо парсинг для всіх активних джерел ────
    from src.application.use_cases.startup import StartupUseCase
    from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository

    async with container.db_session() as session:
        result = await StartupUseCase(
            source_repo=SqlAlchemySourceRepository(session),
            task_queue=container.task_queue,
        ).execute()

    logger.info(
        "Startup: %d sources → %d tasks enqueued",
        result.sources_found, result.tasks_enqueued,
    )

    # ── 5. Periodic scheduler ─────────────────────────────────────────────────
    scheduler = _start_scheduler(container)

    yield  # ← FastAPI обробляє запити
    
    logger.info("Shutting down application...")
    # ── Shutdown ──────────────────────────────────────────────────────────────
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    await container.close()
    logger.info("App shutdown complete")


def _start_scheduler(container):
    """
    Запускає APScheduler для periodic re-scheduling всіх джерел.

    Якщо apscheduler не встановлений — пропускаємо (не критично для dev).

    Celery beat:
      Якщо використовується Celery — замість APScheduler краще використати
      Celery Beat. В такому випадку цей scheduler можна вимкнути.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning(
            "apscheduler not installed — periodic scheduling disabled. "
            "Install with: pip install apscheduler"
        )
        return None

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _schedule_all_sources_job,
        trigger="interval",
        minutes=5,
        id="schedule_all_sources",
        replace_existing=True,
        name="Re-schedule all active sources",
    )

    scheduler.start()
    logger.info("Scheduler started: re-scheduling sources every 5 minutes")
    return scheduler


async def _schedule_all_sources_job() -> None:
    """
    Periodic job: ставить schedule_all_sources в чергу.

    Сама логіка — в handle_schedule_all_sources (workers/handlers.py).
    Тут тільки enqueue.
    """
    from src.config.container import get_container
    container = get_container()
    task_id = await container.task_queue.enqueue("schedule_all_sources")
    logger.debug("Periodic schedule_all_sources enqueued: task_id=%s", task_id[:8])


def create_app() -> FastAPI:
    app = FastAPI(
        title="News Parser API",
        version="0.2.0",
        lifespan=lifespan,
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", # Зверни увагу: без слеша (/) в кінці!
            "http://127.0.0.1:5173"
        ],
        allow_credentials=True,
        allow_methods=["*"], # Дозволяє всі методи (GET, POST, PUT, DELETE тощо)
        allow_headers=["*"], # Дозволяє всі заголовки
    )
    from src.presentation.api.routes import sources, feed, articles, health
    app.include_router(health.router,   prefix="/api/v1/health",   tags=["health"])
    app.include_router(articles.router, prefix="/api/v1/articles", tags=["articles"])
    # app.include_router(auth.router,    prefix="/api/v1/auth",    tags=["auth"])
    app.include_router(sources.router, prefix="/api/v1/sources", tags=["sources"])
    app.include_router(feed.router,    prefix="/api/v1/feed",    tags=["feed"])


    return app


app = create_app()
