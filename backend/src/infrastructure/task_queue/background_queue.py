# infrastructure/task_queue/background_queue.py
"""
Проста реалізація ITaskQueue через FastAPI BackgroundTasks / asyncio.
Не залежить від Celery — легко замінюється.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from typing import Any

from application.ports import ITaskQueue

logger = logging.getLogger(__name__)

# Реєстр задач — infrastructure реєструє свої функції
_TASK_REGISTRY: dict[str, Any] = {}


def register_task(name: str):
    """Декоратор для реєстрації функції як іменованої задачі."""
    def decorator(fn):
        _TASK_REGISTRY[name] = fn
        return fn
    return decorator


class InMemoryTaskQueue(ITaskQueue):
    """
    Dev-реалізація: задачі виконуються в asyncio background.
    В production замінити на CeleryTaskQueue (той самий інтерфейс).
    """

    def __init__(self) -> None:
        self._statuses: dict[str, str] = {}

    async def enqueue(self, task_name: str, *args: Any, **kwargs: Any) -> str:
        task_id = str(uuid.uuid4())
        self._statuses[task_id] = "pending"

        handler = _TASK_REGISTRY.get(task_name)
        if handler is None:
            logger.error("Unknown task: %s", task_name)
            self._statuses[task_id] = "failed"
            return task_id

        async def _run():
            self._statuses[task_id] = "in_progress"
            try:
                await handler(*args, **kwargs)
                self._statuses[task_id] = "completed"
            except Exception as exc:
                logger.exception("Task %s failed: %s", task_name, exc)
                self._statuses[task_id] = "failed"

        asyncio.create_task(_run())
        return task_id

    async def get_status(self, task_id: str) -> str:
        return self._statuses.get(task_id, "unknown")