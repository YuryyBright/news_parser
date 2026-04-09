# infrastructure/persistence/repositories/feed_repo.py
from __future__ import annotations

import logging
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models import (
    FeedSnapshotModel, FeedItemModel, ArticleModel,
    UserFeedbackModel, ReadHistoryModel,
)
from src.domain.feed.entities import FeedSnapshot, FeedItem, FeedItemRef
from src.domain.feed.repositories import IFeedRepository, IFeedbackRepository, UserFeedback

logger = logging.getLogger(__name__)


class SqlAlchemyFeedRepository(IFeedRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── читання ─────────────────────────────────────────────────────────────

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

        read_history_exists = (
            select(1)
            .select_from(ReadHistoryModel)
            .where(
                and_(
                    ReadHistoryModel.article_id == FeedItemModel.article_id,
                    ReadHistoryModel.user_id == str(user_id),
                )
            )
            .correlate(FeedItemModel)
            .exists()
        )

        PastFeedItem = aliased(FeedItemModel)
        PastFeedSnapshot = aliased(FeedSnapshotModel)
        past_read_exists = (
            select(1)
            .select_from(PastFeedItem)
            .join(PastFeedSnapshot, PastFeedItem.snapshot_id == PastFeedSnapshot.id)
            .where(
                and_(
                    PastFeedSnapshot.user_id == str(user_id),
                    PastFeedItem.article_id == FeedItemModel.article_id,
                    PastFeedItem.status == "read",
                )
            )
            .correlate(FeedItemModel)
            .exists()
        )

        items_result = await self._session.execute(
            select(
                FeedItemModel,
                ArticleModel,
                read_history_exists.label("in_history"),
                past_read_exists.label("in_past_feed"),
            )
            .join(ArticleModel, FeedItemModel.article_id == ArticleModel.id)
            .where(FeedItemModel.snapshot_id == snap_row.id)
            .order_by(FeedItemModel.rank)
        )

        items = []
        for item, article, in_history, in_past_feed in items_result.all():
            is_actually_read = item.status == "read" or in_history or in_past_feed
            items.append(
                FeedItem(
                    id=UUID(item.id),                       # ← str → UUID
                    snapshot_id=UUID(item.snapshot_id),     # ← str → UUID
                    article_id=UUID(item.article_id),       # ← str → UUID  (ГОЛОВНИЙ ФІХ)
                    rank=item.rank,
                    score=item.score,
                    language=getattr(article, "language", "") or "",
                    status="read" if is_actually_read else "unread",
                    article_title=article.title or "",
                    article_url=article.url or "",
                    article_published_at=getattr(article, "published_at", None),
                )
            )

        return FeedSnapshot(
            id=UUID(snap_row.id),
            user_id=UUID(snap_row.user_id),
            generated_at=snap_row.generated_at,
            items=items,
        )

    # ─── запис ───────────────────────────────────────────────────────────────

    async def save_snapshot(self, snapshot: FeedSnapshot) -> None:
        snap_row = FeedSnapshotModel(
            id=str(snapshot.id),
            user_id=str(snapshot.user_id),
            generated_at=snapshot.generated_at,
        )
        self._session.add(snap_row)
        for item in snapshot.items:
            self._session.add(self._item_to_model(item))
        await self._session.flush()
        logger.debug(
            "Saved initial snapshot id=%s user=%s items=%d",
            snapshot.id, snapshot.user_id, len(snapshot.items),
        )

    async def append_items(self, snapshot_id: UUID, items: list[FeedItem]) -> None:
        for item in items:
            self._session.add(self._item_to_model(item))
        await self._session.flush()
        logger.debug("Appended %d items to snapshot=%s", len(items), snapshot_id)

    # ─── дії ─────────────────────────────────────────────────────────────────

    async def find_active_item(self, user_id: UUID, article_id: UUID) -> FeedItemRef | None:
        result = await self._session.execute(
            select(FeedItemModel)
            .join(FeedSnapshotModel, FeedItemModel.snapshot_id == FeedSnapshotModel.id)
            .where(
                FeedSnapshotModel.user_id == str(user_id),
                FeedItemModel.article_id == str(article_id),
            )
            .order_by(FeedSnapshotModel.generated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return FeedItemRef(id=UUID(row.id), status=row.status)

    async def mark_item_read(self, feed_item_id: UUID) -> None:
        await self._session.execute(
            update(FeedItemModel)
            .where(FeedItemModel.id == str(feed_item_id))
            .values(status="read")
        )
        await self._session.flush()

    # ─── хелпер ──────────────────────────────────────────────────────────────

    @staticmethod
    def _item_to_model(item: FeedItem) -> FeedItemModel:
        return FeedItemModel(
            id=str(item.id),
            snapshot_id=str(item.snapshot_id),
            article_id=str(item.article_id),
            rank=item.rank,
            score=item.score,
            status=item.status,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Feedback Repository
# ══════════════════════════════════════════════════════════════════════════════

class SqlAlchemyFeedbackRepository(IFeedbackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> UserFeedback | None:
        result = await self._session.execute(
            select(UserFeedbackModel).where(UserFeedbackModel.id == str(id))
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return self._row_to_entity(row)

    async def save(self, feedback: UserFeedback) -> None:
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
        await self.save(entity)

    async def delete(self, id: UUID) -> None:
        await self._session.execute(
            delete(UserFeedbackModel).where(UserFeedbackModel.id == str(id))
        )
        await self._session.flush()

    async def list(self) -> list[UserFeedback]:
        result = await self._session.execute(select(UserFeedbackModel))
        return [self._row_to_entity(r) for r in result.scalars().all()]

    async def get_by_user_article(self, user_id: UUID, article_id: UUID) -> UserFeedback | None:
        result = await self._session.execute(
            select(UserFeedbackModel).where(
                UserFeedbackModel.user_id == str(user_id),
                UserFeedbackModel.article_id == str(article_id),
            )
        )
        row = result.scalar_one_or_none()
        return self._row_to_entity(row) if row else None

    async def submit_feedback(self, feedback: UserFeedback) -> None:
        await self.save(feedback)

    @staticmethod
    def _row_to_entity(row: UserFeedbackModel) -> UserFeedback:
        return UserFeedback(
            id=UUID(row.id),
            user_id=UUID(row.user_id),
            article_id=UUID(row.article_id),
            liked=row.liked,
            created_at=row.created_at,
        )