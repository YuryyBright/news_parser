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

from sqlalchemy import select, update, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.dtos.feed_dto import FeedSnapshotView, FeedItemView
from infrastructure.persistence.models import (
    FeedSnapshotModel, FeedItemModel, ArticleModel,
)

logger = logging.getLogger(__name__)


class SqlAlchemyFeedRepository:
    """
    Репозиторій не реалізує domain interface напряму —
    Feed є application-рівневою концепцією (не окремий bounded context).
    Повертає DTO напряму, щоб уникнути зайвого шару маппінгу.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_snapshot(self, user_id: UUID) -> FeedSnapshotView | None:
        """
        Повертає актуальний snapshot або None якщо немає / всі stale.
        Snapshot вважається stale якщо is_stale=True.
        """
        result = await self._session.execute(
            select(FeedSnapshotModel)
            .where(
                FeedSnapshotModel.user_id == str(user_id),
                FeedSnapshotModel.is_stale.is_(False),
            )
            .options(
                selectinload(FeedSnapshotModel.items)
                .selectinload(FeedItemModel.article)
            )
            .order_by(FeedSnapshotModel.generated_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _snapshot_to_view(model) if model else None

    async def save_snapshot(
        self,
        user_id: UUID,
        ranked_items: list[tuple[UUID, float]],  # [(article_id, score), ...]
    ) -> FeedSnapshotView:
        """
        Створює новий snapshot.
        Попередній snapshot НЕ видаляється — помічається як stale.

        Args:
            ranked_items: список (article_id, score) вже відсортований за rank.
        """
        # Інвалідуємо попередні
        await self._invalidate_user_snapshots(user_id)

        snapshot = FeedSnapshotModel(
            id=str(uuid4()),
            user_id=str(user_id),
            is_stale=False,
            generated_at=datetime.now(timezone.utc),
        )
        self._session.add(snapshot)
        await self._session.flush()  # отримуємо snapshot.id

        items = [
            FeedItemModel(
                id=str(uuid4()),
                snapshot_id=snapshot.id,
                article_id=str(article_id),
                rank=rank,
                score=score,
                status="unread",
            )
            for rank, (article_id, score) in enumerate(ranked_items, start=1)
        ]
        self._session.add_all(items)
        await self._session.flush()

        # Перечитуємо з eager-loaded articles для формування view
        return await self._load_snapshot_view(snapshot.id)

    async def mark_item_read(self, user_id: UUID, article_id: UUID) -> bool:
        """
        Позначає статтю як прочитану в активному snapshot юзера.
        Повертає True якщо оновлення відбулось.
        """
        # Знаходимо активний snapshot
        snapshot_result = await self._session.execute(
            select(FeedSnapshotModel.id)
            .where(
                FeedSnapshotModel.user_id == str(user_id),
                FeedSnapshotModel.is_stale.is_(False),
            )
            .order_by(FeedSnapshotModel.generated_at.desc())
            .limit(1)
        )
        snapshot_id = snapshot_result.scalar_one_or_none()
        if not snapshot_id:
            return False

        result = await self._session.execute(
            update(FeedItemModel)
            .where(
                FeedItemModel.snapshot_id == snapshot_id,
                FeedItemModel.article_id == str(article_id),
                FeedItemModel.status == "unread",
            )
            .values(status="read")
        )
        await self._session.flush()
        return result.rowcount > 0

    async def invalidate_for_user(self, user_id: UUID) -> None:
        """
        Позначити всі snapshot'и юзера як stale.
        Викликати після появи нових статей або після feedback.
        """
        await self._invalidate_user_snapshots(user_id)

    # ─── Private ─────────────────────────────────────────────────────────────

    async def _invalidate_user_snapshots(self, user_id: UUID) -> None:
        await self._session.execute(
            update(FeedSnapshotModel)
            .where(
                FeedSnapshotModel.user_id == str(user_id),
                FeedSnapshotModel.is_stale.is_(False),
            )
            .values(is_stale=True)
        )
        await self._session.flush()

    async def _load_snapshot_view(self, snapshot_id: str) -> FeedSnapshotView:
        result = await self._session.execute(
            select(FeedSnapshotModel)
            .where(FeedSnapshotModel.id == snapshot_id)
            .options(
                selectinload(FeedSnapshotModel.items)
                .selectinload(FeedItemModel.article)
            )
        )
        model = result.scalar_one()
        return _snapshot_to_view(model)


# ─── Feedback ─────────────────────────────────────────────────────────────────

# infrastructure/persistence/repositories/feedback_repo.py
# (в одному файлі з feed_repo для простоти — при потребі розбити)

from infrastructure.persistence.models import (
    RelevanceFeedbackModel, FilterCriteriaModel, UserProfileModel,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


class SqlAlchemyFeedbackRepository:
    """
    Зберігання feedback та оновлення Bayesian prior у FilterCriteria.

    Bayesian prior = (likes + α) / (total + α + β)
    де α=1, β=1 (слабкий prior 0.5 при холодному старті).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_feedback(
        self,
        user_id: UUID,
        article_id: UUID,
        liked: bool,
        score_at_feedback: float = 0.0,
    ) -> None:
        """
        Зберігає або оновлює feedback.
        Після збереження перераховує Bayesian prior у criteria.
        """
        # Upsert feedback (ON CONFLICT UPDATE для SQLite)
        stmt = (
            sqlite_insert(RelevanceFeedbackModel)
            .values(
                id=str(uuid4()),
                user_id=str(user_id),
                article_id=str(article_id),
                liked=liked,
                score_at_feedback=score_at_feedback,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "article_id"],
                set_={"liked": liked, "score_at_feedback": score_at_feedback},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Перерахувати Bayesian prior
        await self._update_bayesian_prior(user_id)

    async def get_user_feedback(
        self, user_id: UUID, article_id: UUID
    ) -> bool | None:
        """None якщо feedback ще не було."""
        result = await self._session.execute(
            select(RelevanceFeedbackModel.liked)
            .where(
                RelevanceFeedbackModel.user_id == str(user_id),
                RelevanceFeedbackModel.article_id == str(article_id),
            )
        )
        row = result.scalar_one_or_none()
        return row  # True/False/None

    async def _update_bayesian_prior(self, user_id: UUID) -> None:
        """
        Bayesian оновлення: prior = (likes + 1) / (total + 2)
        Weak prior: α=β=1 → при нулі feedback prior = 0.5
        """
        from sqlalchemy import func as sa_func

        # Підраховуємо статистику feedback для юзера
        stats = await self._session.execute(
            select(
                sa_func.count(RelevanceFeedbackModel.id).label("total"),
                sa_func.sum(
                    RelevanceFeedbackModel.liked.cast(Integer)
                ).label("likes"),
            )
            .where(RelevanceFeedbackModel.user_id == str(user_id))
        )
        row = stats.one()
        total: int = row.total or 0
        likes: int = row.likes or 0

        # α=1, β=1 (Laplace smoothing)
        new_prior = (likes + 1) / (total + 2)

        # Знаходимо criteria через user_profile
        profile_result = await self._session.execute(
            select(UserProfileModel.id)
            .where(UserProfileModel.user_id == str(user_id))
        )
        profile_id = profile_result.scalar_one_or_none()
        if not profile_id:
            return

        await self._session.execute(
            update(FilterCriteriaModel)
            .where(FilterCriteriaModel.user_profile_id == profile_id)
            .values(feedback_prior=new_prior, feedback_count=total)
        )
        await self._session.flush()

        logger.debug(
            "Bayesian prior updated: user=%s total=%d likes=%d prior=%.3f",
            user_id, total, likes, new_prior,
        )


# ─── Mappers (локальні, тільки для feed) ──────────────────────────────────────

def _snapshot_to_view(model: FeedSnapshotModel) -> FeedSnapshotView:
    return FeedSnapshotView(
        id=UUID(model.id),
        generated_at=model.generated_at,
        items=[_item_to_view(item) for item in (model.items or [])],
    )


def _item_to_view(item: FeedItemModel) -> FeedItemView:
    article = item.article
    return FeedItemView(
        article_id=UUID(item.article_id),
        rank=item.rank,
        score=item.score,
        status=item.status,
        article_title=article.title if article else "",
        article_url=article.url if article else "",
        article_relevance_score=article.relevance_score if article else 0.0,
        article_published_at=article.published_at if article else None,
    )