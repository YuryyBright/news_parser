# presentation/api/routes/feed.py
"""
Feed router — персоналізований фід для користувача.

Endpoints:
  GET   /feed/{user_id}                   — отримати згенерований фід
  PATCH /feed/{user_id}/read/{article_id} — позначити статтю як прочитану
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dtos.feed_dto import FeedSnapshotView, FeedItemView
from src.config.container import Container, get_container
from src.presentation.api.schemas.feed import FeedResponse, FeedArticleResponse

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# FEED GENERATION & RETRIEVAL
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{user_id}",
    response_model=FeedResponse,
    summary="Отримати персоналізований фід",
)
async def get_feed(
    user_id: UUID,
    container: Container = Depends(get_container),
) -> FeedResponse:
    """
    Повернути персоналізований фід для юзера.
    Якщо свіжий snapshot є — повертається кешований. Якщо ні — будується новий.
    """
    async with container.db_session() as session:
        snapshot: FeedSnapshotView = await container.build_feed_uc(session).get_or_build(user_id)
        
    items = sorted(snapshot.items, key=lambda x: x.rank)
    return FeedResponse(
        snapshot_id=snapshot.id,
        generated_at=snapshot.generated_at,
        items=[_feed_item_to_response(item) for item in items],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FEED ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/{user_id}/read/{article_id}",
    status_code=status.HTTP_200_OK,
    summary="Позначити статтю як прочитану",
)
async def mark_read(
    user_id: UUID,
    article_id: UUID,
    container: Container = Depends(get_container),
) -> dict:
    """Позначити статтю як прочитану в активному snapshot."""
    async with container.db_session() as session:
        # Уся логіка пошуку активного снепшоту і оновлення статусу делегується Use Case
        success = await container.mark_article_read_uc(session).execute(
            user_id=user_id, 
            article_id=article_id
        )
        
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Active feed item not found or already read"
        )
        
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation mappers
# ═══════════════════════════════════════════════════════════════════════════════

def _feed_item_to_response(item: FeedItemView) -> FeedArticleResponse:
    return FeedArticleResponse(
        article_id=item.article_id,
        rank=item.rank,
        score=item.score,
        status=item.status,
        title=item.article_title,
        url=item.article_url,
        relevance_score=item.article_relevance_score,
        published_at=item.article_published_at,
    )