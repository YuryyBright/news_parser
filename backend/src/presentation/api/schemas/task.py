# presentation/api/schemas/task.py
"""
HTTP-схеми для Tasks endpoints.

TaskInfo (application DTO) → TaskResponse (HTTP schema).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskResponse(BaseModel):
    """Відповідь для одної задачі."""
    task_id: str
    task_name: str
    status: str          # pending | in_progress | completed | failed | cancelled
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    kwargs: dict[str, Any] = {}
    error: str | None = None
    result: Any = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Відповідь для списку задач."""
    total: int
    tasks: list[TaskResponse]


class TriggerResponse(BaseModel):
    """Відповідь після запуску нової задачі."""
    task_id: str
    task_name: str
    status: str = "pending"
    message: str
