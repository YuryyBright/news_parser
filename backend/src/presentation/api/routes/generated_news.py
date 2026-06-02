# presentation/api/routes/generated_news.py
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.config.container import Container, get_container
from src.presentation.api.schemas.generated_news import (
    GeneratedNewsListResponse,
    GeneratedNewsResponse,
)

router = APIRouter()

SortDir = Literal["asc", "desc"]


@router.get("/", response_model=GeneratedNewsListResponse)
async def list_generated_news(
    language: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, description="Пошук по тексту"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort_dir: SortDir = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    container: Container = Depends(get_container),
) -> GeneratedNewsListResponse:
    async with container.db_session() as session:
        repo = container.generated_news_repo(session)
        items, total = await repo.list_filtered(
            language=language,
            status=status_filter,
            q=q,
            date_from=date_from,
            date_to=date_to,
            sort_dir=sort_dir,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

    return GeneratedNewsListResponse(
        items=[GeneratedNewsResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{news_id}", response_model=GeneratedNewsResponse)
async def get_generated_news(
    news_id: UUID,
    container: Container = Depends(get_container),
) -> GeneratedNewsResponse:
    async with container.db_session() as session:
        repo = container.generated_news_repo(session)
        item = await repo.get_by_id(news_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return GeneratedNewsResponse.model_validate(item)


@router.patch("/{news_id}/publish", response_model=GeneratedNewsResponse)
async def publish_to_telegram(
    news_id: UUID,
    container: Container = Depends(get_container),
) -> GeneratedNewsResponse:
    """Вручну публікує новину в Telegram і змінює статус на published."""
    async with container.db_session() as session:
        repo = container.generated_news_repo(session)
        item = await repo.get_by_id(news_id)
        if not item:
            raise HTTPException(status_code=404, detail="Not found")
        if item.status == "published":
            raise HTTPException(status_code=409, detail="Already published")

        # Відправка в Telegram якщо notifier підключений
        if container._telegram_notifier is not None:
            try:
                await container._telegram_notifier.send_text(item.rewritten_text)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Telegram error: {exc}")

        updated = await repo.mark_published(news_id)

    return GeneratedNewsResponse.model_validate(updated)