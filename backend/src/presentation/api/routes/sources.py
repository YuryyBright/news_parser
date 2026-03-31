# presentation/api/routes/sources.py
"""
Sources router — повний набір ендпоінтів.

Endpoints:
  GET    /sources/              — список джерел
  POST   /sources/              — додати джерело
  DELETE /sources/{id}          — деактивувати джерело
  POST   /sources/{id}/trigger  — вручну запустити парсинг
  GET    /sources/tasks/        — список задач (з фільтрами)
  GET    /sources/tasks/{id}    — статус конкретної задачі
  DELETE /sources/tasks/{id}    — скасувати задачу
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dtos.source_dto import AddSourceCommand, SourceView
from src.application.ports.task_queue import TaskInfo
from src.application.use_cases.add_source import SourceAlreadyExistsError
from src.domain.feed.exceptions import SourceNotFoundError
from src.config.container import Container, get_container
from src.presentation.api.schemas.source import SourceCreateRequest, SourceResponse
from src.presentation.api.schemas.task import TaskListResponse, TaskResponse, TriggerResponse

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=list[SourceResponse],
    summary="Список джерел новин",
)
async def list_sources(
    active_only: bool = Query(default=True, description="Тільки активні джерела"),
    container: Container = Depends(get_container),
) -> list[SourceResponse]:
    async with container.db_session() as session:
        views: list[SourceView] = await container.list_sources_uc(session).execute(
            active_only=active_only
        )
    return [_source_to_response(v) for v in views]


@router.post(
    "/",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Додати нове джерело",
)
async def add_source(
    body: SourceCreateRequest,
    container: Container = Depends(get_container),
) -> SourceResponse:
    """
    201 — джерело додано
    409 — URL вже існує
    422 — невалідні дані (невідомий source_type або interval < 60)
    """
    cmd = AddSourceCommand(
        name=body.name,
        url=str(body.url),
        source_type=body.source_type,
        fetch_interval_seconds=body.fetch_interval_seconds,
    )
    try:
        async with container.db_session() as session:
            view: SourceView = await container.add_source_uc(session).execute(cmd)
    except SourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _source_to_response(view)


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Деактивувати джерело (soft-delete)",
)
async def deactivate_source(
    source_id: UUID,
    container: Container = Depends(get_container),
) -> None:
    try:
        async with container.db_session() as session:
            await container.deactivate_source_uc(session).execute(source_id)
    except SourceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{source_id}/trigger",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Вручну запустити парсинг джерела",
)
async def trigger_ingest(
    source_id: UUID,
    container: Container = Depends(get_container),
) -> TriggerResponse:
    """
    Ставить задачу ingest_source в чергу.
    Виконання асинхронне — відповідь 202 Accepted.
    """
    async with container.db_session() as session:
        views = await container.list_sources_uc(session).execute(active_only=False)
    if not any(v.id == source_id for v in views):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    task_id = await container.task_queue.enqueue(
        "ingest_source",
        source_id=str(source_id),
    )
    return TriggerResponse(
        task_id=task_id,
        task_name="ingest_source",
        status="pending",
        message=f"Ingest task queued for source {source_id}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/tasks/",
    response_model=TaskListResponse,
    summary="Список фонових задач",
)
async def list_tasks(
    task_name: str | None = Query(
        default=None,
        description="Фільтр по імені: ingest_source | process_articles | schedule_all_sources",
    ),
    task_status: str | None = Query(
        default=None,
        alias="status",
        description="Фільтр по статусу: pending | in_progress | completed | failed | cancelled",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    container: Container = Depends(get_container),
) -> TaskListResponse:
    tasks: list[TaskInfo] = await container.task_queue.list_tasks(
        task_name=task_name,
        status=task_status,
        limit=limit,
    )
    return TaskListResponse(
        total=len(tasks),
        tasks=[_task_to_response(t) for t in tasks],
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Статус конкретної задачі",
)
async def get_task(
    task_id: str,
    container: Container = Depends(get_container),
) -> TaskResponse:
    info: TaskInfo | None = await container.task_queue.get_info(task_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return _task_to_response(info)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Скасувати задачу",
)
async def cancel_task(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict:
    cancelled = await container.task_queue.cancel(task_id)
    if not cancelled:
        info = await container.task_queue.get_info(task_id)
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task '{task_id}' not found",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel task in status '{info.status}'",
        )
    return {"task_id": task_id, "status": "cancelled"}


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation mappers
# ═══════════════════════════════════════════════════════════════════════════════

def _source_to_response(view: SourceView) -> SourceResponse:
    return SourceResponse(
        id=view.id,
        name=view.name,
        url=view.url,
        source_type=view.source_type,
        fetch_interval_seconds=view.fetch_interval_seconds,
        is_active=view.is_active,
        created_at=view.created_at,
    )


def _task_to_response(info: TaskInfo) -> TaskResponse:
    return TaskResponse(
        task_id=info.task_id,
        task_name=info.task_name,
        status=info.status,
        created_at=info.created_at,
        started_at=info.started_at,
        finished_at=info.finished_at,
        kwargs=info.kwargs,
        error=info.error,
        result=info.result,
    )
