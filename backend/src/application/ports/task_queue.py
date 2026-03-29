# application/ports/task_queue.py
"""
Порт черги задач.

Application визначає ЩО потрібно — infrastructure реалізує ЯК.
Use cases та роутери знають тільки про ITaskQueue та TaskInfo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence


@dataclass(frozen=True)
class TaskInfo:
    """
    Інформація про задачу — незалежна від реалізації черги.

    Однаковий формат для InMemoryQueue і CeleryQueue.
    Presentation отримує TaskInfo і конвертує в HTTP-схему.
    """
    task_id: str
    task_name: str
    status: str                   # pending | in_progress | completed | failed
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    kwargs: dict[str, Any]        # аргументи з якими запущено задачу
    error: str | None = None      # повідомлення помилки якщо status=failed
    result: Any = None            # результат якщо status=completed


class ITaskQueue(ABC):
    """
    Абстрактна черга задач.

    Реалізації:
      - InMemoryTaskQueue  — asyncio, для dev/test
      - CeleryTaskQueue    — production з Redis/RabbitMQ broker
    """

    @abstractmethod
    async def enqueue(self, task_name: str, **kwargs: Any) -> str:
        """
        Поставити задачу в чергу.

        Повертає task_id (str UUID).
        kwargs — серіалізуються в JSON, тому тільки прості типи.
        """
        ...

    @abstractmethod
    async def get_info(self, task_id: str) -> TaskInfo | None:
        """
        Повна інформація про задачу.
        Повертає None якщо task_id невідомий.
        """
        ...

    @abstractmethod
    async def list_tasks(
        self,
        task_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskInfo]:
        """
        Список задач з фільтрацією.

        task_name: фільтр по імені ("ingest_source", "process_articles"...)
        status:    фільтр по статусу
        limit:     максимум записів
        """
        ...

    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """
        Скасувати задачу (якщо ще не запущена).
        Повертає True якщо скасовано, False якщо неможливо.
        """
        ...

class ISourceRepository(ABC):
    @abstractmethod
    async def list_active(self) -> Sequence[Any]: # Replace Any with your Source entity
        """Retrieve all sources where is_active is True."""
        ...