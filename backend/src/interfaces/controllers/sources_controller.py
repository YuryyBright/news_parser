# interfaces/api/controllers/sources_controller.py
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from interfaces.api.schemas import (
    CreateSourceRequest, UpdateSourceRequest,
    SourceResponse, PaginatedResponse, TaskResponse,
)
from interfaces.api.dependencies import get_current_user, get_container_dep
from infrastructure.config.container import Container
from infrastructure.persistence.database import get_session
from application.ingestion.use_cases import (
    ListSourcesUseCase, CreateSourceUseCase,
    UpdateSourceUseCase, DeleteSourceUseCase, TriggerFetchUseCase,
)
from infrastructure.persistence.models import UserModel

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SourceResponse])
async def list_sources(
    limit:       Annotated[int,         Query(ge=1, le=100)] = 20,
    offset:      Annotated[int,         Query(ge=0)]         = 0,
    source_type: Annotated[str | None,  Query()]             = None,
    is_active:   Annotated[bool | None, Query()]             = None,
    session:     AsyncSession = Depends(get_session),
    container:   Container    = Depends(get_container_dep),
    _user:       UserModel    = Depends(get_current_user),
):
    uc = ListSourcesUseCase(container.source_repo(session))
    return await uc.execute(limit=limit, offset=offset,
                            source_type=source_type, is_active=is_active)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    session:   AsyncSession = Depends(get_session),
    container: Container    = Depends(get_container_dep),
    _user:     UserModel    = Depends(get_current_user),
):
    uc = ListSourcesUseCase(container.source_repo(session))
    return await uc.get_one(source_id)


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body:      CreateSourceRequest,
    session:   AsyncSession = Depends(get_session),
    container: Container    = Depends(get_container_dep),
    _user:     UserModel    = Depends(get_current_user),
):
    uc = CreateSourceUseCase(container.source_repo(session))
    return await uc.execute(body)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    body:      UpdateSourceRequest,
    session:   AsyncSession = Depends(get_session),
    container: Container    = Depends(get_container_dep),
    _user:     UserModel    = Depends(get_current_user),
):
    uc = UpdateSourceUseCase(container.source_repo(session))
    return await uc.execute(source_id, body)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    session:   AsyncSession = Depends(get_session),
    container: Container    = Depends(get_container_dep),
    _user:     UserModel    = Depends(get_current_user),
):
    uc = DeleteSourceUseCase(container.source_repo(session))
    await uc.execute(source_id)


@router.post("/{source_id}/fetch", response_model=TaskResponse)
async def trigger_fetch(
    source_id: str,
    session:   AsyncSession = Depends(get_session),
    container: Container    = Depends(get_container_dep),
    _user:     UserModel    = Depends(get_current_user),
):
    task_id = await container.task_queue.enqueue("fetch_source", source_id)
    return TaskResponse(task_id=task_id, status="queued")