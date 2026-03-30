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
"""
Task handlers — async функції що виконуються чергою задач.

Handler — це glue-код між task queue і container:
  1. Отримує kwargs (прості типи — str, int)
  2. get_container() → відкриває db_session
  3. container.{дія}_uc(session) → use case (вся логіка залежностей в container)
  4. Викликає use case
  5. Логує результат

Handlers НЕ імпортують use cases напряму — це порушення dependency rule
(infrastructure не має знати про application шар напряму, тільки через container).
"""

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

    container = get_container()

    async with container.db_session() as session:
        result = await container.ingest_source_uc(session).execute(UUID(source_id))

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

    container = get_container()

    result = await container.process_articles_uc_standalone().execute()

    logger.info(
        "process_articles done: processed=%d failed=%d",
        result.processed, result.failed,
    )

    if result.failed and not result.processed:
        raise RuntimeError(
            f"All {result.failed} articles failed. Errors: {result.errors[:3]}"
        )

    return {"processed": result.processed, "failed": result.failed}


async def handle_schedule_all_sources() -> dict:
    """
    Scheduler handler — ставить ingest_source в чергу для всіх активних джерел.

    Запускається periodically (APScheduler або Celery beat).
    """
    from src.config.container import get_container

    container = get_container()

    async with container.db_session() as session:
        result = await container.startup_uc(session).execute()

    logger.info(
        "schedule_all_sources done: sources=%d enqueued=%d",
        result.sources_found, result.tasks_enqueued,
    )

    return {
        "sources_found": result.sources_found,
        "tasks_enqueued": result.tasks_enqueued,
    }