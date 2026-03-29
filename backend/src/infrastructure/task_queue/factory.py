# infrastructure/task_queue/factory.py
"""
Фабрика черги задач — вибирає між Celery і InMemory.

Стратегія:
  1. Якщо use_celery=True → пробуємо підключитись до Celery
  2. Якщо Celery недоступний → fallback на InMemoryTaskQueue з попередженням
  3. Якщо use_celery=False → одразу InMemoryTaskQueue
"""
from __future__ import annotations

import logging

from src.application.ports.task_queue import ITaskQueue

logger = logging.getLogger(__name__)


def build_task_queue(cfg) -> ITaskQueue:   # cfg: TaskQueueSettings
    """
    Повертає готовий до роботи ITaskQueue.
    Викликається один раз при ініціалізації Container.
    """
    if cfg.use_celery:
        return _try_celery(cfg)
    return _make_in_memory()


def _try_celery(cfg) -> ITaskQueue:
    try:
        from src.infrastructure.task_queue.celery_queue import CeleryTaskQueue
        queue = CeleryTaskQueue(
            broker=cfg.celery_broker,
            backend=cfg.celery_result_backend,
        )
        queue.ping()   # швидкий health-check — кидає якщо broker недоступний
        logger.info("Task queue: Celery (broker=%s)", cfg.celery_broker)
        return queue
    except Exception as exc:
        logger.warning(
            "Celery unavailable (%s), falling back to InMemoryTaskQueue. "
            "Tasks will be lost on restart.",
            exc,
        )
        return _make_in_memory()


def _make_in_memory() -> ITaskQueue:
    from src.infrastructure.task_queue.background_queue import InMemoryTaskQueue
    logger.info("Task queue: InMemory (asyncio)")
    return InMemoryTaskQueue()
