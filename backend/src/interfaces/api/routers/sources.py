# presentation/api/routes/sources.py
"""
Контролер (роутер) для джерел.

Presentation знає:
- HTTP (FastAPI, Pydantic schemas)
- application use cases (через container)

НЕ знає: SQLAlchemy, ChromaDB, моделі БД.
"""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from src.config.container import Container, get_container
from src.infrastructure.persistence.database import AsyncSessionFactory
from src.infrastructure.persistence.repositories.source_repo import SourceRepository
from application.ports import SourceDTO

router = APIRouter()


# ─── Pydantic schemas (живуть тільки в presentation) ─────────────────────────

class SourceCreate(BaseModel):
    name: str
    url: HttpUrl
    source_type: str = "rss"
    fetch_interval_sec: int = 300

class SourceResponse(BaseModel):
    id: UUID
    name: str
    url: str
    source_type: str
    is_active: bool
    fetch_interval_sec: int


# ─── Dependency: сесія + контейнер ───────────────────────────────────────────

async def get_source_repo(container: Container = Depends(get_container)):
    async with container.make_session() as session:
        yield SourceRepository(session)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[SourceResponse])
async def list_sources(repo: SourceRepository = Depends(get_source_repo)):
    sources = await repo.get_all_active()
    return [_to_response(s) for s in sources]


@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    container: Container = Depends(get_container),
):
    from uuid import uuid4
    dto = SourceDTO(
        id=uuid4(),
        name=body.name,
        url=str(body.url),
        source_type=body.source_type,
        config={},
        fetch_interval_sec=body.fetch_interval_sec,
        is_active=True,
    )
    async with container.make_session() as session:
        async with session.begin():
            await SourceRepository(session).save(dto)
    return _to_response(dto)


@router.post("/{source_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fetch(
    source_id: UUID,
    container: Container = Depends(get_container),
):
    """Вручну запустити парсинг одного джерела."""
    task_id = await container.task_queue.enqueue(
        "ingest_source", source_id=str(source_id)
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/{source_id}/status/{task_id}")
async def get_task_status(
    source_id: UUID,
    task_id: str,
    container: Container = Depends(get_container),
):
    status_value = await container.task_queue.get_status(task_id)
    return {"task_id": task_id, "status": status_value}


def _to_response(dto: SourceDTO) -> SourceResponse:
    return SourceResponse(
        id=dto.id,
        name=dto.name,
        url=dto.url,
        source_type=dto.source_type,
        is_active=dto.is_active,
        fetch_interval_sec=dto.fetch_interval_sec,
    )