# ═══════════════════════════════════════════════════════════
# api/routers/health.py
# ═══════════════════════════════════════════════════════════
"""
Healthcheck — мінімальний роутер для перевірки стану сервісу.
Показує статистику статей за статусами.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.settings import get_settings
from infrastructure.persistence.database import get_session
from infrastructure.persistence.repositories.article_repo import ArticleRepository

router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    repo   = ArticleRepository(session)
    counts = await repo.count_by_status()
    return {
        "status": "ok",
        "articles": counts,
    }


# ═══════════════════════════════════════════════════════════
# api/routers/sources.py
# ═══════════════════════════════════════════════════════════
"""
Sources router — CRUD для джерел новин.

Контролер у DDD — дуже тонкий:
  - валідує вхідні дані (Pydantic)
  - викликає один use case або repo
  - повертає відповідь

БЕЗ бізнес-логіки в контролері.
"""
from __future__ import annotations
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.models import SourceModel
from src.config.settings import get_settings

router = APIRouter()
settings = get_settings()


# ─── Pydantic schemas (DTO — Data Transfer Objects) ──────────────────────────

class SourceIn(BaseModel):
    name: str
    url: HttpUrl
    source_type: str = "rss"          # rss | atom | html | api
    fetch_interval_sec: int = 300
    config: dict = {}


class SourceOut(BaseModel):
    id: UUID
    name: str
    url: str
    source_type: str
    is_active: bool
    fetch_interval_sec: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SourceOut])
async def list_sources(
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
):
    """Список всіх джерел. ?active_only=false — включно з неактивними."""
    stmt = select(SourceModel)
    if active_only:
        stmt = stmt.where(SourceModel.is_active == True)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceIn,
    session: AsyncSession = Depends(get_session),
):
    """Додати нове джерело для парсингу."""
    # Перевірка дублікату URL
    existing = await session.execute(
        select(SourceModel).where(SourceModel.url == str(payload.url))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with URL '{payload.url}' already exists",
        )

    source = SourceModel(
        name=payload.name,
        url=str(payload.url),
        source_type=payload.source_type,
        fetch_interval_sec=payload.fetch_interval_sec,
        config=payload.config,
        is_active=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """М'яке видалення — джерело позначається як неактивне."""
    source = await session.get(SourceModel, str(source_id))
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_active = False
    await session.commit()


@router.post("/{source_id}/fetch-now", status_code=status.HTTP_202_ACCEPTED)
async def trigger_fetch(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Примусово запустити fetch для конкретного джерела (не чекаючи scheduler).
    Використовується для тестування нових джерел.
    """
    source = await session.get(SourceModel, str(source_id))
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from infrastructure.persistence.repositories.article_repo import ArticleRepository
    from application.use_cases.ingestion.fetch_pipeline import FetchPipelineUseCase

    repo     = ArticleRepository(session)
    fetch_uc = FetchPipelineUseCase(session, repo)
    new_count = await fetch_uc.run_for_source(source)

    return {"message": f"Fetched {new_count} new articles from '{source.name}'"}


# ═══════════════════════════════════════════════════════════
# api/routers/articles.py
# ═══════════════════════════════════════════════════════════
"""Articles router — перегляд статей та feedback."""
from __future__ import annotations
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.database import get_session
from infrastructure.persistence.models import ArticleModel, RelevanceFeedbackModel

router = APIRouter()


class ArticleOut(BaseModel):
    id: UUID
    title: str
    url: str
    language: str
    status: str
    relevance_score: float
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackIn(BaseModel):
    user_id: UUID
    liked: bool


@router.get("", response_model=list[ArticleOut])
async def list_articles(
    status: str | None = None,
    min_score: float = 0.0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ArticleModel)
        .where(ArticleModel.relevance_score >= min_score)
        .order_by(ArticleModel.relevance_score.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(ArticleModel.status == status)

    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    article = await session.get(ArticleModel, str(article_id))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/{article_id}/feedback", status_code=201)
async def submit_feedback(
    article_id: UUID,
    payload: FeedbackIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Записати лайк / дизлайк від юзера.
    Після цього ScoreArticlesUseCase оновить feedback_prior.

    У DDD feedback — це Domain Event що призводить до зміни FilterCriteria.
    """
    article = await session.get(ArticleModel, str(article_id))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Upsert feedback
    existing = await session.execute(
        select(RelevanceFeedbackModel).where(
            RelevanceFeedbackModel.user_id    == str(payload.user_id),
            RelevanceFeedbackModel.article_id == str(article_id),
        )
    )
    fb = existing.scalar_one_or_none()

    if fb is None:
        fb = RelevanceFeedbackModel(
            user_id=str(payload.user_id),
            article_id=str(article_id),
            liked=payload.liked,
            score_at_feedback=article.relevance_score,
        )
        session.add(fb)
    else:
        fb.liked = payload.liked

    # Оновити Bayesian prior у criteria
    from infrastructure.persistence.repositories.criteria_repo import CriteriaRepository
    criteria_repo = CriteriaRepository(session)
    criteria = await criteria_repo.get_for_user(payload.user_id)

    if criteria:
        # Простий Bayesian update: prior = (prior * count + signal) / (count + 1)
        signal = 1.0 if payload.liked else 0.0
        new_count = criteria.feedback_count + 1
        new_prior = (criteria.feedback_prior * criteria.feedback_count + signal) / new_count
        await criteria_repo.update_feedback_prior(
            UUID(criteria.id), new_prior, new_count
        )

    await session.commit()
    return {"status": "ok", "liked": payload.liked}


# ═══════════════════════════════════════════════════════════
# api/routers/feed.py
# ═══════════════════════════════════════════════════════════
"""Feed router — персоналізований фід для користувача."""
from __future__ import annotations
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.database import get_session
from infrastructure.persistence.repositories.article_repo import ArticleRepository
from infrastructure.persistence.repositories.criteria_repo import CriteriaRepository
from application.use_cases.feed.build_feed import BuildFeedUseCase

router = APIRouter()


class FeedArticleOut(BaseModel):
    article_id: UUID
    rank: int
    score: float
    status: str
    title: str
    url: str
    relevance_score: float
    published_at: datetime | None

    model_config = {"from_attributes": True}


class FeedOut(BaseModel):
    snapshot_id: UUID
    generated_at: datetime
    items: list[FeedArticleOut]


@router.get("/{user_id}", response_model=FeedOut)
async def get_feed(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Повернути персоналізований фід для юзера.

    Якщо свіжий snapshot є — повернути його (кешований).
    Якщо ні — побудувати новий (може зайняти кілька секунд).

    Score = relevance_score * recency_decay_factor
    """
    uc = BuildFeedUseCase(
        session=session,
        article_repo=ArticleRepository(session),
        criteria_repo=CriteriaRepository(session),
    )
    snapshot = await uc.get_or_build(user_id)

    items = [
        FeedArticleOut(
            article_id=UUID(item.article_id),
            rank=item.rank,
            score=item.score,
            status=item.status,
            title=item.article.title if item.article else "",
            url=item.article.url if item.article else "",
            relevance_score=item.article.relevance_score if item.article else 0.0,
            published_at=item.article.published_at if item.article else None,
        )
        for item in sorted(snapshot.items, key=lambda x: x.rank)
    ]

    return FeedOut(
        snapshot_id=UUID(snapshot.id),
        generated_at=snapshot.generated_at,
        items=items,
    )


@router.patch("/{user_id}/read/{article_id}")
async def mark_read(
    user_id: UUID,
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Позначити статтю як прочитану в активному snapshot."""
    from sqlalchemy import select, update
    from infrastructure.persistence.models import FeedItemModel, FeedSnapshotModel

    await session.execute(
        update(FeedItemModel)
        .where(
            FeedItemModel.article_id == str(article_id),
            FeedItemModel.snapshot_id.in_(
                select(FeedSnapshotModel.id).where(
                    FeedSnapshotModel.user_id == str(user_id),
                    FeedSnapshotModel.is_stale == False,
                )
            ),
        )
        .values(status="read")
    )
    await session.commit()
    return {"status": "ok"}