# presentation/api/routes/feed.py
from __future__ import annotations

from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dtos.feed_dto import FeedSnapshotView, FeedItemView
from src.config.container import Container, get_container
from src.presentation.api.schemas.feed import FeedResponse, FeedArticleResponse, FeedPageResponse

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# FEED GENERATION & RETRIEVAL
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{user_id}",
    response_model=FeedPageResponse,
    summary="Отримати персоналізований фід (з пагінацією)",
)
async def get_feed(
    user_id: UUID,
    offset: int = Query(default=0, ge=0, description="Скільки статей пропустити"),
    limit: int = Query(default=20, ge=1, le=100, description="Кількість статей"),
    filter: Literal["all", "unread", "read"] = Query(
        default="all", description="Фільтр за статусом прочитання"
    ),
    container: Container = Depends(get_container),
) -> FeedPageResponse:
    async with container.db_session() as session:
        snapshot: FeedSnapshotView = await container.build_feed_uc(session).get_or_build(user_id)

    items = snapshot.items

    # Фільтрація за статусом
    if filter == "unread":
        items = [i for i in items if i.status != "read"]
    elif filter == "read":
        items = [i for i in items if i.status == "read"]

    # Сортуємо за датою публікації (найновіші — перші).
    # НЕ за rank: нові статті отримують вищий rank (append),
    # але мають бути видні вгорі фіду.
    def _sort_key(item: FeedItemView):
        pub = item.article_published_at
        return pub.timestamp() if pub else 0.0

    items = sorted(items, key=_sort_key, reverse=True)

    total = len(items)
    page_items = items[offset: offset + limit]
    has_more = (offset + limit) < total

    return FeedPageResponse(
        snapshot_id=snapshot.id,
        generated_at=snapshot.generated_at,
        total=total,
        offset=offset,
        limit=limit,
        has_more=has_more,
        items=[_feed_item_to_response(item) for item in page_items],
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
    async with container.db_session() as session:
        success = await container.mark_article_read_uc(session).execute(
            user_id=user_id,
            article_id=article_id,
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active feed item not found or already read",
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
        language=item.language,
        url=item.article_url,
        relevance_score=item.article_relevance_score,
        published_at=item.article_published_at,
    )