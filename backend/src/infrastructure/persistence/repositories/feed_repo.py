# infrastructure/persistence/repositories/feed_repo.py
"""
SqlAlchemyFeedRepository — зберігання FeedSnapshot та FeedItem.

Відповідальності:
  - get_active_snapshot()  — останній не-stale snapshot для юзера
  - save_snapshot()        — зберегти новий snapshot з items
  - mark_item_read()       — змінити статус item на "read"
  - invalidate_snapshots() — позначити всі snapshots юзера як stale
                             (викликається після нових статей або feedback)
"""
from __future__ import annotations

import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import select, update, Integer, delete, and_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from src.infrastructure.persistence.models import (
    FeedSnapshotModel, FeedItemModel, ArticleModel, UserFeedbackModel, ReadHistoryModel
)
from src.domain.feed.entities import FeedSnapshot as FeedSnapshot, FeedItem, FeedItemRef
from src.domain.feed.repositories import IFeedRepository, IFeedbackRepository, UserFeedback
logger = logging.getLogger(__name__)


class SqlAlchemyFeedRepository(IFeedRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_snapshot(self, user_id: UUID) -> FeedSnapshot | None:

        snap_result = await self._session.execute(
            select(FeedSnapshotModel)
            .where(FeedSnapshotModel.user_id == str(user_id))
            .order_by(FeedSnapshotModel.generated_at.desc())
            .limit(1)
        )
        snap_row = snap_result.scalar_one_or_none()
        if snap_row is None:
            return None

        # Підзапит 1: Чи є стаття в загальній історії прочитаного
        read_history_exists = (
            select(1)
            .select_from(ReadHistoryModel)  # <-- ЯВНО ВКАЗУЄМО ТАБЛИЦЮ
            .where(
                and_(
                    ReadHistoryModel.article_id == FeedItemModel.article_id,
                    ReadHistoryModel.user_id == str(user_id)
                )
            )
            .correlate(FeedItemModel)
            .exists()
        )

        # Підзапит 2: Чи була стаття позначена як "read" у будь-якому з минулих фідів
        PastFeedItem = aliased(FeedItemModel)
        PastFeedSnapshot = aliased(FeedSnapshotModel)
        
        past_read_exists = (
            select(1)
            .select_from(PastFeedItem)  # <-- ЯВНО ВКАЗУЄМО ЛІВУ СТОРОНУ ДЛЯ JOIN
            .join(PastFeedSnapshot, PastFeedItem.snapshot_id == PastFeedSnapshot.id)
            .where(
                and_(
                    PastFeedSnapshot.user_id == str(user_id),
                    PastFeedItem.article_id == FeedItemModel.article_id,
                    PastFeedItem.status == "read"
                )
            )
            .correlate(FeedItemModel)
            .exists()
        )

        # Робимо спільний запит
        items_result = await self._session.execute(
            select(
                FeedItemModel, 
                ArticleModel, 
                read_history_exists.label("in_history"), 
                past_read_exists.label("in_past_feed")
            )
            .join(ArticleModel, FeedItemModel.article_id == ArticleModel.id)
            .where(FeedItemModel.snapshot_id == snap_row.id)
            .order_by(FeedItemModel.rank)
        )

        items = []
        for item, article, in_history, in_past_feed in items_result.all():
            # Навіть якщо поточний item.status == "unread", але ми знайшли сліди 
            # прочитання в базі, ми примусово віддаємо "read"
            is_actually_read = item.status == "read" or in_history or in_past_feed
            actual_status = "read" if is_actually_read else "unread"

            items.append(
                FeedItem(
                    id=item.id,
                    snapshot_id=item.snapshot_id,
                    article_id=item.article_id,
                    rank=item.rank,
                    score=item.score,
                    status=actual_status,
                    article_title=article.title or "",
                    article_url=article.url or "",
                    article_published_at=getattr(article, "published_at", None),
                )
            )

        return FeedSnapshot(
            id=snap_row.id,
            user_id=snap_row.user_id,
            generated_at=snap_row.generated_at,
            items=items,
        )
    async def save_snapshot(self, snapshot: FeedSnapshot) -> None:
        snap_row = FeedSnapshotModel(
            id=str(snapshot.id),               # Explicitly cast to string
            user_id=str(snapshot.user_id),     # Explicitly cast to string
            generated_at=snapshot.generated_at,
        )
        self._session.add(snap_row)

        for item in snapshot.items:
            self._session.add(FeedItemModel(
                id=str(item.id),                 # Explicitly cast to string
                snapshot_id=str(item.snapshot_id), # Explicitly cast to string
                article_id=str(item.article_id),   # Explicitly cast to string
                rank=item.rank,
                score=item.score,
                status=item.status,
            ))

        await self._session.flush()
        logger.debug(
            "Saved snapshot id=%s user=%s items=%d",
            snapshot.id, snapshot.user_id, len(snapshot.items),
        )

    async def find_active_item(
        self, user_id: UUID, article_id: UUID
    ) -> FeedItemRef | None:

        result = await self._session.execute(
            select(FeedItemModel)
            .join(FeedSnapshotModel, FeedItemModel.snapshot_id == FeedSnapshotModel.id)
            .where(
                # Explicitly cast UUIDs to strings to match the String(36) column type
                FeedSnapshotModel.user_id == str(user_id),
                FeedItemModel.article_id == str(article_id),
                # Optional: Uncomment if "active" implies a specific status
                # FeedItemModel.status != "deleted" 
            )
            .order_by(FeedSnapshotModel.generated_at.desc())
            .limit(1)
        )
        
        row = result.scalar_one_or_none()
        
        if row is None:
            return None
            
        return FeedItemRef(id=row.id, status=row.status)

    async def mark_item_read(self, feed_item_id: UUID) -> None:
        await self._session.execute(
            update(FeedItemModel)
            .where(FeedItemModel.id == str(feed_item_id)) # Cast to string
            .values(status="read")
        )
        await self._session.flush()


# ══════════════════════════════════════════════════════════════════════════════
# Feedback Repository
# ══════════════════════════════════════════════════════════════════════════════

class SqlAlchemyFeedbackRepository(IFeedbackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> UserFeedback | None:
        """Fetch a single UserFeedback by its ID."""
        result = await self._session.execute(
            select(UserFeedbackModel).where(UserFeedbackModel.id == str(id))
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
            
        return UserFeedback(
            id=UUID(row.id),
            user_id=UUID(row.user_id),
            article_id=UUID(row.article_id),
            liked=row.liked,
            created_at=row.created_at,
        )

    async def save(self, feedback: UserFeedback) -> None:
        # Cast feedback.id to a string here:
        existing = await self._session.get(UserFeedbackModel, str(feedback.id))
        
        if existing is not None:
            existing.liked = feedback.liked
            existing.created_at = feedback.created_at
        else:
            self._session.add(UserFeedbackModel(
                id=str(feedback.id),               
                user_id=str(feedback.user_id),     
                article_id=str(feedback.article_id), 
                liked=feedback.liked,
                created_at=feedback.created_at,
            ))
        await self._session.flush()

    async def update(self, entity: UserFeedback) -> None:
        """Update an existing UserFeedback (acts same as save in this context)."""
        await self.save(entity)

    async def delete(self, id: UUID) -> None:
        """Delete a UserFeedback by its ID."""
        await self._session.execute(
            delete(UserFeedbackModel).where(UserFeedbackModel.id == str(id))
        )
        await self._session.flush()

    async def list(self) -> list[UserFeedback]:
        """Retrieve all UserFeedback records."""
        result = await self._session.execute(select(UserFeedbackModel))
        rows = result.scalars().all()
        
        return [
            UserFeedback(
                id=UUID(row.id),
                user_id=UUID(row.user_id),
                article_id=UUID(row.article_id),
                liked=row.liked,
                created_at=row.created_at,
            )
            for row in rows
        ]

    # --- Custom IFeedbackRepository Methods ---

    async def get_by_user_article(
        self, user_id: UUID, article_id: UUID
    ) -> UserFeedback | None:
        """Fetch a specific user's feedback for a specific article."""
        result = await self._session.execute(
            select(UserFeedbackModel).where(
                UserFeedbackModel.user_id == str(user_id),
                UserFeedbackModel.article_id == str(article_id),
            )
        )
        row = result.scalar_one_or_none()
        
        if row is None:
            return None
            
        return UserFeedback(
            id=UUID(row.id),
            user_id=UUID(row.user_id),
            article_id=UUID(row.article_id),
            liked=row.liked,
            created_at=row.created_at,
        )

    async def submit_feedback(self, feedback: UserFeedback) -> None:
        """
        Satisfies the abstract 'submit_feedback' requirement. 
        In standard CRUD, this is identical to 'save()'.
        """
        await self.save(feedback)