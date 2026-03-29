# presentation/api/routes/articles.py
"""
Articles router — перегляд статей та збереження фідбеку.

Endpoints:
  GET  /articles/                 — список статей (з фільтрами)
  GET  /articles/{article_id}     — отримати статтю за ID
  POST /articles/{article_id}/feedback — додати/оновити фідбек

Роутер відповідає ТІЛЬКИ за HTTP (викликає відповідні Use Cases).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dtos.article_dto import ArticleView, SubmitFeedbackCommand
# from application.use_cases.get_article import ArticleNotFoundError
from src.config.container import Container, get_container
from src.presentation.api.schemas.article import (
    ArticleResponse,
    FeedbackCreateRequest,
    FeedbackResponse,
)

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# ARTICLES CRUD & LISTING
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=list[ArticleResponse],
    summary="Список статей",
)
async def list_articles(
    status_filter: str | None = Query(default=None, alias="status", description="Фільтр по статусу"),
    min_score: float = Query(default=0.0, description="Мінімальна оцінка релевантності"),
    limit: int = Query(default=50, ge=1, le=200),
    container: Container = Depends(get_container),
) -> list[ArticleResponse]:
    async with container.db_session() as session:
        views: list[ArticleView] = await container.list_articles_uc(session).execute(
            status=status_filter,
            min_score=min_score,
            limit=limit,
        )
    return [_article_to_response(v) for v in views]


@router.get(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="Отримати статтю за ID",
)
async def get_article(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> ArticleResponse:
    try:
        async with container.db_session() as session:
            view: ArticleView = await container.get_article_uc(session).execute(article_id)
            return _article_to_response(view)
    # except ArticleNotFoundError:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    except ValueError as exc:
        # domain validation: невідомий article_id
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{article_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Надіслати фідбек (лайк/дизлайк) для статті",
)
async def submit_feedback(
    article_id: UUID,
    payload: FeedbackCreateRequest,
    container: Container = Depends(get_container),
) -> FeedbackResponse:
    """
    Записати лайк / дизлайк від юзера та перерахувати Bayesian prior.
    Уся доменна логіка виконується всередині submit_feedback_uc.
    """
    cmd = SubmitFeedbackCommand(
        user_id=payload.user_id,
        article_id=article_id,
        liked=payload.liked,
    )
    
    try:
        async with container.db_session() as session:
            await container.submit_feedback_uc(session).execute(cmd)
    # except ArticleNotFoundError:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    except ValueError as exc:
        # domain validation: невідомий article_id
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        
    return FeedbackResponse(status="ok", liked=payload.liked)


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation mappers
# ═══════════════════════════════════════════════════════════════════════════════

def _article_to_response(view: ArticleView) -> ArticleResponse:
    return ArticleResponse(
        id=view.id,
        title=view.title,
        url=view.url,
        language=view.language,
        status=view.status,
        relevance_score=view.relevance_score,
        published_at=view.published_at,
        created_at=view.created_at,
    )