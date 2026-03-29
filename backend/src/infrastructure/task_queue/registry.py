# infrastructure/task_queue/registry.py
"""
Єдине місце реєстрації задач.

Викликається ТІЛЬКИ з bootstrap (lifespan у main.py).
Ні application, ні окремі workers не викликають register_task напряму.

Патерн:
  registry.py знає про handlers.py
  handlers.py знає про use cases (через container)
  use cases не знають ні про registry, ні про handlers
"""
from __future__ import annotations

import logging

from src.infrastructure.task_queue.background_queue import register_task

logger = logging.getLogger(__name__)


def register_all_tasks() -> None:
    """
    Реєструє всі відомі задачі в _REGISTRY.
    Має викликатись одразу після init_container().
    """
    # Імпортуємо handlers тут — не на рівні модуля
    # (щоб уникнути circular imports при тестуванні)
    from src.infrastructure.workers.handlers import (
        handle_ingest_source,
        handle_process_articles,
        handle_schedule_all_sources,
    )

    register_task("ingest_source", handle_ingest_source)
    register_task("process_articles", handle_process_articles)
    register_task("schedule_all_sources", handle_schedule_all_sources)

    logger.info(
        "Tasks registered: ingest_source, process_articles, schedule_all_sources"
    )
