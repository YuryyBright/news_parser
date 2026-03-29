# application/use_cases/startup.py
"""
Use case: дії при старті програми.

При запуску FastAPI lifespan — цей use case:
1. Перевіряє всі активні джерела
2. Ставить в чергу завдання на парсинг
3. Нічого не імпортує з infrastructure!
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

from src.application.ports.task_queue import ISourceRepository, ITaskQueue

logger = logging.getLogger(__name__)


@dataclass
class StartupResult:
    sources_found: int
    tasks_enqueued: int


class StartupUseCase:
    """
    Запускається один раз при старті застосунку.
    Ставить кожне активне джерело в чергу на парсинг.
    """

    def __init__(
        self,
        source_repo: ISourceRepository,
        task_queue: ITaskQueue,
    ) -> None:
        self._sources = source_repo
        self._task_queue = task_queue

    async def execute(self) -> StartupResult:
        sources = await self._sources.list_active()
        logger.info("Startup: found %d active sources", len(sources))

        enqueued = 0
        for source in sources:
            try:
                task_id = await self._task_queue.enqueue(
                    "ingest_source",
                    source_id=str(source.id),
                )
                logger.info("Enqueued source %s → task %s", source.name, task_id)
                enqueued += 1
            except Exception as exc:
                logger.error("Failed to enqueue source %s: %s", source.name, exc)

        return StartupResult(sources_found=len(sources), tasks_enqueued=enqueued)