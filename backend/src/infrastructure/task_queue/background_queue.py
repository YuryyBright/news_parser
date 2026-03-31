# infrastructure/task_queue/background_queue.py
"""
InMemoryTaskQueue — asyncio реалізація ITaskQueue.

Використовується коли Celery недоступний (dev, test, lightweight deploy).
Задачі виконуються як asyncio.Task в тому самому процесі.

Обмеження (порівняно з Celery):
  - задачі губляться при перезапуску процесу
  - немає worker-процесів — всі задачі в одному event loop
  - немає retry з backoff (можна додати при потребі)
  - список задач зберігається в пам'яті (обмежений _MAX_HISTORY)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.application.ports.task_queue import ITaskQueue, TaskInfo

logger = logging.getLogger(__name__)

# Реєстр: task_name → async callable
# Заповнюється через register_task() при bootstrap
_REGISTRY: dict[str, Any] = {}

# Скільки завершених задач тримаємо в пам'яті
_MAX_HISTORY = 500


def register_task(name: str, handler) -> None:
    """
    Зареєструвати async callable під іменем.

    Викликається тільки з bootstrap/registry.py — не з use cases.

    Args:
        name:    "ingest_source", "process_articles" тощо
        handler: async def handler(**kwargs) -> Any
    """
    _REGISTRY[name] = handler
    logger.debug("Task registered: %s", name)


class _TaskRecord:
    """
    Внутрішній стан однієї задачі.
    Не виходить назовні — конвертується в TaskInfo через to_info().
    """
    __slots__ = (
        "task_id", "task_name", "status",
        "created_at", "started_at", "finished_at",
        "kwargs", "error", "result", "_asyncio_task",
    )

    def __init__(self, task_id: str, task_name: str, kwargs: dict) -> None:
        self.task_id = task_id
        self.task_name = task_name
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.kwargs = kwargs
        self.error: str | None = None
        self.result: Any = None
        self._asyncio_task: asyncio.Task | None = None

    def to_info(self) -> TaskInfo:
        return TaskInfo(
            task_id=self.task_id,
            task_name=self.task_name,
            status=self.status,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            kwargs=self.kwargs,
            error=self.error,
            result=self.result,
        )


class InMemoryTaskQueue(ITaskQueue):
    """
    Dev/lightweight реалізація черги задач.
    Thread-safe для asyncio (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._tasks: dict[str, _TaskRecord] = {}
        self._locks: dict[str, asyncio.Lock] = {}  

    async def enqueue(self, task_name: str, **kwargs: Any) -> str:
        handler = _REGISTRY.get(task_name)
        if handler is None:
            raise ValueError(
                f"Unknown task '{task_name}'. "
                f"Available: {list(_REGISTRY.keys())}"
            )

        task_id = str(uuid.uuid4())
        record = _TaskRecord(task_id=task_id, task_name=task_name, kwargs=kwargs)
        self._tasks[task_id] = record

        # Run via the new lock wrapper
        record._asyncio_task = asyncio.create_task(
            self._run_with_lock(task_name, record, handler, kwargs),
            name=f"{task_name}:{task_id[:8]}",
        )

        logger.info("Task enqueued: %s id=%s kwargs=%s", task_name, task_id[:8], kwargs)
        return task_id

    async def _run_with_lock(self, task_name: str, record: _TaskRecord, handler, kwargs: dict) -> None:
        """Executes the task with a lock to prevent race conditions on identical tasks."""
        # Create a unique lock key (e.g., "process_articles:{}" or "ingest_source:{'source_id': '...'}")
        lock_key = f"{task_name}:{kwargs}"
        
        if lock_key not in self._locks:
            self._locks[lock_key] = asyncio.Lock()
        
        async with self._locks[lock_key]:
            # Only run if it wasn't cancelled while waiting for the lock
            if record.status != "cancelled":
                await self._run(record, handler, kwargs)

    async def _run(self, record: _TaskRecord, handler, kwargs: dict) -> None:
        record.status = "in_progress"
        record.started_at = datetime.now(timezone.utc)
        try:
            record.result = await handler(**kwargs)
            record.status = "completed"
            logger.info(
                "Task completed: %s id=%s",
                record.task_name, record.task_id[:8],
            )
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            logger.exception(
                "Task failed: %s id=%s error=%s",
                record.task_name, record.task_id[:8], exc,
            )
        finally:
            record.finished_at = datetime.now(timezone.utc)
            self._trim_history()

    def _trim_history(self) -> None:
        """Видаляємо старі завершені задачі щоб не накопичувати пам'ять."""
        done = [
            (tid, r) for tid, r in self._tasks.items()
            if r.status in ("completed", "failed")
        ]
        if len(done) > _MAX_HISTORY:
            # Видаляємо найстаріші
            to_remove = sorted(done, key=lambda x: x[1].created_at)
            for tid, _ in to_remove[: len(done) - _MAX_HISTORY]:
                del self._tasks[tid]

    async def get_info(self, task_id: str) -> TaskInfo | None:
        record = self._tasks.get(task_id)
        return record.to_info() if record else None

    async def list_tasks(
        self,
        task_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskInfo]:
        records = list(self._tasks.values())

        if task_name:
            records = [r for r in records if r.task_name == task_name]
        if status:
            records = [r for r in records if r.status == status]

        # Найновіші першими
        records.sort(key=lambda r: r.created_at, reverse=True)
        return [r.to_info() for r in records[:limit]]

    async def cancel(self, task_id: str) -> bool:
        record = self._tasks.get(task_id)
        if record is None:
            return False
        if record.status != "pending":
            return False  # вже запущена або завершена

        if record._asyncio_task and not record._asyncio_task.done():
            record._asyncio_task.cancel()

        record.status = "cancelled"
        record.finished_at = datetime.now(timezone.utc)
        return True
