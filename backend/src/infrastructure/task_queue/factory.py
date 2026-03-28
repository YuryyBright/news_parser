# infrastructure/task_queue/factory.py


from __future__ import annotations
from application.ports import ITaskQueue
from infrastructure.config.settings import TaskQueueSettings

def build_task_queue(cfg: TaskQueueSettings) -> ITaskQueue:
    if cfg.use_celery:
        return _try_celery(cfg)
    return _background_queue()

def _try_celery(cfg: TaskQueueSettings) -> ITaskQueue:
    try:
        from infrastructure.task_queue.celery_queue import CeleryTaskQueue
        queue = CeleryTaskQueue(cfg.celery_broker, cfg.celery_result_backend)
        queue.ping()  # Перевіряємо з'єднання з брокером
        return queue
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Celery unavailable ({e}), falling back to BackgroundTaskQueue"
        )
        return _background_queue()

def _background_queue() -> ITaskQueue:
    from infrastructure.task_queue.background_queue import BackgroundTaskQueue
    return BackgroundTaskQueue()