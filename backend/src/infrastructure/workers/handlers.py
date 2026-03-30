# infrastructure/workers/handlers.py
"""
Task handlers — async функції що виконуються чергою задач.

Handler — це glue-код між task queue і use case:
  1. Отримує kwargs (прості типи — рядки, числа)
  2. Відкриває сесію через container
  3. Будує use case із залежностями
  4. Викликає use case
  5. Логує результат

Handlers знають про:
  ✓ container (сесія, task_queue)
  ✓ use cases
  ✓ infrastructure adapters (fetchers, репозиторії)

Handlers НЕ знають про:
  ✗ FastAPI / HTTP / Pydantic
  ✗ механіку черги (register_task — у registry.py)
"""
from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def handle_ingest_source(source_id: str) -> dict:
    """
    Завантажити та зберегти сирі статті для одного джерела.

    Викликається:
      - При старті (для кожного активного джерела)
      - По scheduler (кожні fetch_interval_seconds)
      - Вручну через POST /sources/{id}/trigger

    Args:
        source_id: str UUID джерела
    """
    from src.config.container import get_container
    from src.application.use_cases.ingest_source import IngestSourceUseCase
    from src.infrastructure.parsers.rss_parser import RssFetcher
    from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
    from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository
    from src.infrastructure.persistence.repositories.fetch_job_repo import SqlAlchemyFetchJobRepository

    container = get_container()

    async with container.db_session() as session:
        result = await IngestSourceUseCase(
            source_repo=SqlAlchemySourceRepository(session),
            raw_article_repo=SqlAlchemyRawArticleRepository(session),
            fetch_job_repo=SqlAlchemyFetchJobRepository(session),
            fetcher=RssFetcher(),
        ).execute(UUID(source_id))

    logger.info(
        "ingest_source done: source=%s fetched=%d saved=%d skipped=%d",
        source_id, result.fetched, result.saved, result.skipped_duplicates,
    )

    # Якщо use case повернув помилку — кидаємо RuntimeError
    # щоб черга зафіксувала задачу як failed
    if result.error:
        raise RuntimeError(result.error)

    return {
        "source_id": source_id,
        "fetched": result.fetched,
        "saved": result.saved,
        "skipped": result.skipped_duplicates,
    }


async def handle_process_articles() -> dict:
    """
    Обробити всі 'pending' статті:
      - визначити мову
      - порахувати relevance score
      - оновити статус → ACCEPTED або REJECTED

    Запускається після handle_ingest_source або окремо по scheduler.
    """
    from src.config.container import get_container
    from src.application.use_cases.process_articles import ProcessArticlesUseCase
    from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository

    container = get_container()

    async with container.db_session() as session:
        result = await ProcessArticlesUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            raw_article_repo=SqlAlchemyRawArticleRepository(session),
        ).execute()

    logger.info(
        "process_articles done: processed=%d failed=%d",
        result.processed, result.failed,
    )

    return {"processed": result.processed, "failed": result.failed}


async def handle_schedule_all_sources() -> dict:
    """
    Scheduler handler — ставить ingest_source в чергу для всіх активних джерел.

    Запускається periodically (APScheduler або Celery beat).
    """
    from src.config.container import get_container
    from src.application.use_cases.startup import StartupUseCase
    from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository

    container = get_container()

    async with container.db_session() as session:
        result = await StartupUseCase(
            source_repo=SqlAlchemySourceRepository(session),
            task_queue=container.task_queue,
        ).execute()

    logger.info(
        "schedule_all_sources done: sources=%d enqueued=%d",
        result.sources_found, result.tasks_enqueued,
    )

    return {
        "sources_found": result.sources_found,
        "tasks_enqueued": result.tasks_enqueued,
    }