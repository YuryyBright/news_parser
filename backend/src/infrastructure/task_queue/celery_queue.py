# infrastructure/task_queue/celery_queue.py
from __future__ import annotations
import asyncio
from celery import Celery
from celery.result import AsyncResult
from application.ports import ITaskQueue

class CeleryTaskQueue(ITaskQueue):
    def __init__(self, broker: str, backend: str) -> None:
        self._app = Celery(
            "news_parser",
            broker=broker,
            backend=backend,
        )
        self._app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_track_started=True,
        )
        self._app.autodiscover_tasks(["infrastructure.workers"])
        
    def ping(self) -> None:
        """Кидає виключення якщо Celery недоступний."""
        self._app.control.ping(timeout=2)
    
    async def enqueue(self, task_name: str, *args: any, **kwargs: any) -> str:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._app.send_task(task_name, args=args, kwargs=kwargs)
        )
        return result.id
    
    async def get_status(self, task_id: str) -> str:
        result = AsyncResult(task_id, app=self._app)
        return {
            "task_id": task_id,
            "status": result.status.lower(),  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE', etc.
            "result": result.result if result.ready() else None,
        }