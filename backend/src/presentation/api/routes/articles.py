# presentation/api/routes/articles.py
"""
Articles router — повний CRUD + feedback.

Endpoints:
  GET    /articles/                     — список
  POST   /articles/                     — створити (адмін)
  GET    /articles/{id}                 — деталі
  PATCH  /articles/{id}                 — оновити поля
  DELETE /articles/{id}                 — видалити
  POST   /articles/{id}/tags            — додати теги
  POST   /articles/{id}/expire          — expire
  POST   /articles/{id}/feedback        — лайк / дизлайк

Роутер ТІЛЬКИ:
  1. Валідує HTTP (Pydantic schemas)
  2. Викликає use case
  3. Ловить ДОМЕННІ exceptions → HTTP status
  Бізнес-логіки тут НЕМАЄ.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dtos.article_dto import (
    AcceptArticleCommand,
    CreateArticleCommand,
    ExpireArticleCommand,
    SubmitFeedbackCommand,
    TagArticleCommand,
    UpdateArticleCommand,
)
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


# ═══════════════════════════════════════════════════════════════════════════════
# READ
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/")
async def list_articles(
    status_filter: str | None = Query(default=None, alias="status"),
    min_score: float = Query(default=0.0),
    language: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: Container = Depends(get_container),
):
    # Схема → доменний фільтр (конвертація в роутері)
    f = ArticleFilter(
        status=ArticleStatus(status_filter) if status_filter else None,
        min_score=min_score,
        language=language,
        limit=limit,
        offset=offset,
    )
    async with container.db_session() as session:
        views = await container.list_articles_uc(session).execute(f)
    return [_to_response(v) for v in views]


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


@router.patch(
    "/{article_id}",
    response_model=ArticleDetailResponse,
    summary="Оновити поля статті",
)
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


@router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити статтю",
)
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
# DOMAIN ACTIONS (state machine transitions)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{article_id}/tags",
    response_model=TagsResponse,
    summary="Додати теги",
)
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


@router.post(
    "/{article_id}/expire",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Позначити статтю як застарілу",
)
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
    summary="Лайк / дизлайк",
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
# Presentation mappers (локальні — не виносити в окремий файл)
# ═══════════════════════════════════════════════════════════════════════════════

# presentation/api/routes/articles.py

# ... (інший код) ...

def _to_response(v) -> ArticleResponse:
    # Отримуємо список об'єктів тегів
    raw_tags = getattr(v, "tags", [])
    
    # Конвертуємо об'єкти Tag у рядки (їхні імена)
    # Якщо там вже рядки, залишаємо як є, якщо об'єкти — беремо .name
    tag_names = [t.name if hasattr(t, "name") else str(t) for t in raw_tags]

    return ArticleResponse(
        id=v.id,
        title=v.title,
        url=v.url,
        language=v.language,
        status=v.status,
        relevance_score=v.relevance_score,
        published_at=v.published_at.value if hasattr(v.published_at, 'value') else v.published_at,
        created_at=v.created_at,
        tags=tag_names,  # Тепер тут список рядків
    )


def _to_detail_response(v) -> ArticleDetailResponse:
    raw_tags = getattr(v, "tags", [])
    tag_names = [t.name if hasattr(t, "name") else str(t) for t in raw_tags]

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
        tags=tag_names,  # Тепер тут список рядків
        source_id=getattr(v, "source_id", None),
    )
