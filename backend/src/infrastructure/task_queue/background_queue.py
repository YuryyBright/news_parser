# infrastructure/task_queue/background_queue.py
# Реєстр зберігає не функції а STRING імена — resolve відбувається lazy
from __future__ import annotations
import asyncio
import importlib
import uuid
from typing import Any

_REGISTRY: dict[str, str] = {}   # task_name → "module.path:function_name"
_RESULTS:  dict[str, dict] = {}


def register_task(name: str, import_path: str) -> None:
    """
    import_path: "infrastructure.workers.handlers:fetch_source"
    Реєстрація без імпорту — resolve тільки при виконанні.
    """
    _REGISTRY[name] = import_path


async def _resolve_and_call(name: str, *args, **kwargs) -> Any:
    import_path = _REGISTRY.get(name)
    if not import_path:
        raise ValueError(f"Unknown task: {name}")

    module_path, fn_name = import_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    fn = getattr(module, fn_name)
    return await fn(*args, **kwargs)


class BackgroundTaskQueue:
    async def enqueue(self, task_name: str, *args: Any, **kwargs: Any) -> str:
        task_id = str(uuid.uuid4())
        _RESULTS[task_id] = {"task_id": task_id, "status": "STARTED"}

        async def _run():
            try:
                result = await _resolve_and_call(task_name, *args, **kwargs)
                _RESULTS[task_id] = {"task_id": task_id, "status": "SUCCESS", "result": result}
            except Exception as e:
                _RESULTS[task_id] = {"task_id": task_id, "status": "FAILURE", "error": str(e)}

        asyncio.create_task(_run())
        return task_id

    async def get_status(self, task_id: str) -> dict:
        return _RESULTS.get(task_id, {"task_id": task_id, "status": "PENDING"})