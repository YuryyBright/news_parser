# infrastructure/task_queue/celery_queue.py
"""
CeleryTaskQueue — production реалізація ITaskQueue.

Вимоги:
  - Redis або RabbitMQ як broker
  - Redis як result backend (для get_info/list_tasks)

Важливо: get_info() та list_tasks() потребують result_backend.
Якщо backend не налаштований — методи повернуть обмежену інформацію.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from celery.result import AsyncResult

from application.ports.task_queue import ITaskQueue, TaskInfo

logger = logging.getLogger(__name__)

# Маппінг Celery статусів → уніфіковані статуси
_STATUS_MAP = {
    "PENDING":  "pending",
    "RECEIVED": "pending",
    "STARTED":  "in_progress",
    "RETRY":    "in_progress",
    "SUCCESS":  "completed",
    "FAILURE":  "failed",
    "REVOKED":  "cancelled",
}


class CeleryTaskQueue(ITaskQueue):

    def __init__(self, broker: str, backend: str) -> None:
        self._app = Celery("news_parser", broker=broker, backend=backend)
        self._app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_track_started=True,
            task_send_sent_event=True,
        )
        # Workers знаходяться в infrastructure.workers
        self._app.autodiscover_tasks(["infrastructure.workers"])

    def ping(self) -> None:
        """Перевірка з'єднання з broker. Кидає виключення якщо недоступний."""
        self._app.control.ping(timeout=2)

    def _run_sync(self, fn, *args, **kwargs):
        """Виконати синхронний Celery виклик через executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def enqueue(self, task_name: str, **kwargs: Any) -> str:
        result = await self._run_sync(
            self._app.send_task, task_name, kwargs=kwargs
        )
        logger.info("Task enqueued via Celery: %s id=%s", task_name, result.id[:8])
        return result.id

    async def get_info(self, task_id: str) -> TaskInfo | None:
        async_result: AsyncResult = await self._run_sync(
            AsyncResult, task_id, self._app
        )
        if async_result is None:
            return None

        raw_status = async_result.status  # "PENDING", "SUCCESS" тощо
        status = _STATUS_MAP.get(raw_status, "pending")

        # Celery не зберігає kwargs в result backend за замовчуванням
        # Якщо потрібно — треба передавати їх окремо або зберігати в Redis
        return TaskInfo(
            task_id=task_id,
            task_name=async_result.name or "unknown",
            status=status,
            created_at=datetime.now(timezone.utc),   # Celery не завжди надає
            started_at=None,
            finished_at=None,
            kwargs={},
            error=str(async_result.result) if status == "failed" else None,
            result=async_result.result if async_result.ready() else None,
        )

    async def list_tasks(
        self,
        task_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskInfo]:
        """
        Celery не має вбудованого API для списку задач без Flower.

        Варіанти:
          1. Використати Celery Flower API (рекомендовано для prod)
          2. Зберігати task_id в Redis/БД при enqueue (простіший підхід)
          3. Використати celery inspect (тільки активні задачі)

        Тут реалізовано варіант 3 — active tasks через inspect.
        Для повної історії — доповни варіантом 2.
        """
        inspect = self._app.control.inspect()

        active = await self._run_sync(inspect.active) or {}
        reserved = await self._run_sync(inspect.reserved) or {}

        all_tasks: list[TaskInfo] = []

        for worker_tasks in [*active.values(), *reserved.values()]:
            for task_data in worker_tasks:
                t_name = task_data.get("name", "unknown")
                if task_name and t_name != task_name:
                    continue

                t_status = "in_progress" if task_data in active.values() else "pending"
                if status and t_status != status:
                    continue

                all_tasks.append(TaskInfo(
                    task_id=task_data["id"],
                    task_name=t_name,
                    status=t_status,
                    created_at=datetime.now(timezone.utc),
                    started_at=None,
                    finished_at=None,
                    kwargs=task_data.get("kwargs", {}),
                ))

        return all_tasks[:limit]

    async def cancel(self, task_id: str) -> bool:
        try:
            await self._run_sync(self._app.control.revoke, task_id, terminate=False)
            return True
        except Exception as exc:
            logger.warning("Failed to cancel task %s: %s", task_id, exc)
            return False
