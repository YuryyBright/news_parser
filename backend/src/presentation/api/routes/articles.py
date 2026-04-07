# presentation/api/routes/articles.py
"""
Articles router — повний CRUD + feedback + preferences + search.

DDD-правила presentation layer:
  ✅ залежить ТІЛЬКИ від Container (який надає use cases)
  ✅ ніяких прямих імпортів з src.infrastructure.*
  ✅ конвертує HTTP-запит → Command/Query → викликає use case → відповідь
  ✅ перехоплює доменні винятки й повертає HTTP-статуси

Endpoints:
  GET    /articles/                 — список (фільтр, сортування, пагінація)
  GET    /articles/search           — full-text пошук (PostgreSQL tsvector)
  GET    /articles/preferences      — вподобані / відхилені статті юзера
  GET    /articles/preferences/stats — статистика вподобань
  POST   /articles/                 — створити (адмін)
  POST   /articles/ingest-url       — поставити URL в чергу на парсинг
  GET    /articles/{id}             — деталі
  PATCH  /articles/{id}             — оновити поля
  DELETE /articles/{id}             — видалити
  POST   /articles/{id}/tags        — додати теги
  POST   /articles/{id}/expire      — expire
  POST   /articles/{id}/feedback    — лайк / дизлайк
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, HttpUrl

from src.application.dtos.article_dto import (
    AcceptArticleCommand,
    CreateArticleCommand,
    ExpireArticleCommand,
    SubmitFeedbackCommand,
    TagArticleCommand,
    UpdateArticleCommand,
)
from src.application.use_cases.article_preferences import (
    GetPreferencesStatsQuery,
    ListByPreferencesQuery,
)
from src.application.use_cases.search_articles import SearchArticlesQuery
from src.config.container import Container, get_container
from src.domain.knowledge.exceptions import ArticleNotFound, DuplicateArticle
from src.domain.knowledge.value_objects import ArticleFilter, ArticleStatus
from src.presentation.api.schemas.article import (
    ArticleCreateRequest,
    ArticleDetailResponse,
    ArticleResponse,
    ArticleUpdateRequest,
    FeedbackCreateRequest,
    FeedbackResponse,
    TagsAddRequest,
    TagsResponse,
)

router = APIRouter()

SortBy  = Literal["created_at", "published_at", "relevance_score"]
SortDir = Literal["asc", "desc"]


# ═══════════════════════════════════════════════════════════════════════════════
# READ — LIST
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", summary="Список статей з фільтрами та пагінацією")
async def list_articles(
    status_filter: str | None = Query(default=None, alias="status"),
    min_score: float = Query(default=0.0),
    language: str | None = Query(default=None),
    tag: str | None = Query(default=None, description="Фільтр по тегу"),
    date_from: datetime | None = Query(default=None, description="Від дати (created_at, ISO8601)"),
    date_to: datetime | None = Query(default=None, description="До дати (created_at, ISO8601)"),
    published_from: datetime | None = Query(default=None),
    published_to: datetime | None = Query(default=None),
    sort_by: SortBy = Query(default="created_at"),
    sort_dir: SortDir = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: UUID | None = Query(default=None, description="UUID юзера — виключає дизлайкнуті статті"),
    container: Container = Depends(get_container),
):
    """
    Повертає сторінку статей.

    Фільтр по тегу тепер передається через ArticleFilter.tag —
    домен знає про нього, репозиторій його підтримує,
    роутер більше не лізе в інфраструктуру напряму.

    user_id (опціонально): виключає статті, які цей юзер дизлайкнув.
    """
    f = ArticleFilter(
        status=ArticleStatus(status_filter) if status_filter else None,
        min_score=min_score,
        language=language,
        tag=tag,
        limit=page_size,
        offset=(page - 1) * page_size,
        date_from=date_from,
        date_to=date_to,
        published_from=published_from,
        published_to=published_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    async with container.db_session() as session:
        uc = container.list_articles_uc(session)
        views = await uc.execute(f, user_id=user_id)
        total = await uc.count(f)

    return {
        "items": [_to_response(v) for v in views],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/search", summary="Full-text пошук статей по title + body")
async def search_articles(
    q: str = Query(..., min_length=2, description="Пошуковий запит"),
    language: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    container: Container = Depends(get_container),
):
    query = SearchArticlesQuery(
        query=q,
        language=language,
        status=ArticleStatus(status_filter) if status_filter else None,
        limit=limit,
    )
    async with container.db_session() as session:
        result = await container.search_articles_uc(session).execute(query)

    return {
        "query": result.query,
        "total": result.total,
        "items": [_to_response(v) for v in result.items],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PREFERENCES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/preferences",
    response_model=list[ArticleResponse],
    summary="Статті за вподобаннями юзера",
)
async def list_by_preferences(
    user_id: UUID = Query(...),
    liked: bool = Query(..., description="true = вподобані, false = відхилені"),
    limit: int = Query(default=100, ge=1, le=200),
    container: Container = Depends(get_container),
) -> list[ArticleResponse]:
    query = ListByPreferencesQuery(user_id=user_id, liked=liked, limit=limit)
    async with container.db_session() as session:
        views = await container.list_by_preferences_uc(session).execute(query)
    return [_to_response(v) for v in views]


@router.get("/preferences/stats", summary="Статистика вподобань юзера")
async def preferences_stats(
    user_id: UUID = Query(...),
    container: Container = Depends(get_container),
) -> dict:
    query = GetPreferencesStatsQuery(user_id=user_id)
    async with container.db_session() as session:
        stats = await container.get_preferences_stats_uc(session).execute(query)
    return {
        "liked": stats.liked_count,
        "disliked": stats.disliked_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# READ — DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{article_id}", response_model=ArticleDetailResponse, summary="Деталі статті")
async def get_article(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> ArticleDetailResponse:
    try:
        async with container.db_session() as session:
            view = await container.get_article_uc(session).execute(article_id)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return _to_detail_response(view)


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/",
    response_model=ArticleDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити статтю (адмін)",
)
async def create_article(
    payload: ArticleCreateRequest,
    container: Container = Depends(get_container),
) -> ArticleDetailResponse:
    cmd = CreateArticleCommand(
        source_id=payload.source_id,
        title=payload.title,
        body=payload.body,
        url=str(payload.url),
        language=payload.language or "unknown",
        published_at=payload.published_at,
    )
    try:
        async with container.db_session() as session:
            view = await container.create_article_uc(session).execute(cmd)
    except DuplicateArticle as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _to_detail_response(view)


@router.patch("/{article_id}", response_model=ArticleDetailResponse, summary="Оновити поля статті")
async def update_article(
    article_id: UUID,
    payload: ArticleUpdateRequest,
    container: Container = Depends(get_container),
) -> ArticleDetailResponse:
    cmd = UpdateArticleCommand(
        article_id=article_id,
        title=payload.title,
        body=payload.body,
        language=payload.language,
    )
    try:
        async with container.db_session() as session:
            view = await container.update_article_uc(session).execute(cmd)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return _to_detail_response(view)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Видалити статтю")
async def delete_article(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> None:
    try:
        async with container.db_session() as session:
            await container.delete_article_uc(session).execute(article_id)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")


# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{article_id}/tags", response_model=TagsResponse, summary="Додати теги")
async def add_tags(
    article_id: UUID,
    payload: TagsAddRequest,
    container: Container = Depends(get_container),
) -> TagsResponse:
    cmd = TagArticleCommand(article_id=article_id, tag_names=payload.tags)
    try:
        async with container.db_session() as session:
            tags = await container.tag_article_uc(session).execute(cmd)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return TagsResponse(tags=tags)


@router.post("/{article_id}/expire", status_code=status.HTTP_204_NO_CONTENT, summary="Expire статтю")
async def expire_article(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> None:
    cmd = ExpireArticleCommand(article_id=article_id)
    try:
        async with container.db_session() as session:
            await container.expire_article_uc(session).execute(cmd)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")


@router.post(
    "/{article_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Лайк / дизлайк статті",
)
async def submit_feedback(
    article_id: UUID,
    payload: FeedbackCreateRequest,
    container: Container = Depends(get_container),
) -> FeedbackResponse:
    cmd = SubmitFeedbackCommand(
        user_id=payload.user_id,
        article_id=article_id,
        liked=payload.liked,
    )
    try:
        async with container.db_session() as session:
            await container.submit_feedback_uc(session).execute(cmd)
    except ArticleNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return FeedbackResponse(status="ok", liked=payload.liked)


# ═══════════════════════════════════════════════════════════════════════════════
# INGEST URL
# ═══════════════════════════════════════════════════════════════════════════════

class IngestUrlRequest(BaseModel):
    url: HttpUrl
    source_id: UUID | None = None


@router.post(
    "/ingest-url",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Поставити URL в чергу на парсинг та обробку",
)
async def ingest_url(
    body: IngestUrlRequest,
    container: Container = Depends(get_container),
) -> dict:
    task_id = await container.task_queue.enqueue(
        "ingest_url",
        url=str(body.url),
        source_id=str(body.source_id) if body.source_id else None,
    )
    return {
        "status": "queued",
        "task_id": task_id,
        "url": str(body.url),
        "message": "Статтю поставлено в чергу на парсинг та обробку",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation mappers
# Отримують ArticleView / ArticleDetailView DTO — не доменні сутності.
# Немає hasattr-duck-typing: контракт гарантований DTO dataclass-ами.
# ═══════════════════════════════════════════════════════════════════════════════

def _to_response(v) -> ArticleResponse:
    return ArticleResponse(
        id=v.id,
        title=v.title,
        url=v.url,
        language=v.language,
        status=v.status,
        relevance_score=v.relevance_score,
        published_at=v.published_at,   # вже datetime | None (розгорнуто в use case)
        created_at=v.created_at,
        tags=v.tags,                   # вже list[str] (розгорнуто в use case)
    )


def _to_detail_response(v) -> ArticleDetailResponse:
    return ArticleDetailResponse(
        id=v.id,
        title=v.title,
        body=v.body,
        url=v.url,
        language=v.language,
        status=v.status,
        relevance_score=v.relevance_score,
        published_at=v.published_at,
        created_at=v.created_at,
        tags=v.tags,
        source_id=v.source_id,
    )