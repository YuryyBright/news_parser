# application/use_cases/build_feed.py
"""
BuildFeedUseCase — один постійний FeedSnapshot на юзера,
який інкрементально поповнюється новими статтями.

Логіка:
  1. Шукаємо існуючий snapshot для user_id
  2. Якщо немає → створюємо новий з усіх accepted статей (з урахуванням фільтрації дизлайків)
  3. Якщо є → шукаємо вглиб бази статті, яких ще немає в snapshot,
              додаємо їх як нові FeedItem в кінець.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.feed.entities import FeedItem, FeedSnapshot
from src.application.dtos.feed_dto import FeedItemView, FeedSnapshotView
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.feed.repositories import IFeedRepository
from src.domain.knowledge.value_objects import ArticleStatus, ArticleFilter

logger = logging.getLogger(__name__)

_DEFAULT_FEED_SIZE = 200   # збільшено: початковий фід до 600 статей (3×200)
_BATCH_SIZE = 100
_MAX_OFFSET = 5000         # збільшено: обходимо всю базу до 5000 статей


class BuildFeedUseCase:

    def __init__(
        self,
        article_repo: IArticleRepository,
        feed_repo: IFeedRepository,
        feed_size: int = _DEFAULT_FEED_SIZE,
    ) -> None:
        self._articles = article_repo
        self._feed = feed_repo
        self._feed_size = feed_size

    async def get_or_build(self, user_id: UUID) -> FeedSnapshotView:
        existing = await self._feed.get_active_snapshot(user_id)

        if existing is None:
            logger.info("No snapshot found, building initial feed: user=%s", user_id)
            snapshot = await self._build_initial(user_id)
            await self._feed.save_snapshot(snapshot)
            return self._to_view(snapshot)

        new_items = await self._fetch_new_items(existing)

        if new_items:
            logger.info(
                "Appending %d new articles to snapshot=%s user=%s",
                len(new_items), existing.id, user_id,
            )
            await self._feed.append_items(existing.id, new_items)
            existing = existing.with_items(existing.items + new_items)
        else:
            logger.debug("Feed up to date: user=%s snapshot=%s", user_id, existing.id)

        return self._to_view(existing)

    # ─────────────────────────────────────────────────────────────────────────

    async def _build_initial(self, user_id: UUID) -> FeedSnapshot:
        articles = await self._articles.find(
            ArticleFilter(
                status=ArticleStatus.ACCEPTED,
                limit=self._feed_size,   # до 600 статей одразу
                min_score=0.65,
                offset=0,
                sort_by="created_at",
                sort_dir="desc",
            ),
            user_id=user_id,
        )
        ranked = self._rank(articles)

        # Фільтруємо дублі за назвою
        unique_articles = []
        seen_titles: set[str] = set()
        for a in ranked:
            title_key = a.title.strip().lower() if a.title else ""
            if title_key not in seen_titles:
                unique_articles.append(a)
                if title_key:
                    seen_titles.add(title_key)

        snapshot_id = uuid4()
        now = datetime.now(timezone.utc)

        items = [
            self._make_item(snapshot_id, article, rank)
            for rank, article in enumerate(unique_articles, start=1)
        ]
        logger.info(
            "Built initial snapshot id=%s user=%s items=%d",
            snapshot_id, user_id, len(items),
        )
        return FeedSnapshot(id=snapshot_id, user_id=user_id, generated_at=now, items=items)

    async def _fetch_new_items(self, snapshot: FeedSnapshot) -> list[FeedItem]:
        """Шукає нові статті пагінацією, доки не знайде всі унікальні."""

        # ВАЖЛИВО: article_id у FeedItem має бути UUID — гарантуємо це тут
        existing_ids: set[UUID] = {
            item.article_id if isinstance(item.article_id, UUID) else UUID(str(item.article_id))
            for item in snapshot.items
        }
        existing_titles: set[str] = {
            item.article_title.strip().lower()
            for item in snapshot.items
            if item.article_title
        }

        new_articles = []
        offset = 0
        max_new = self._feed_size * 3  # підтягуємо до 600 нових за раз

        while len(new_articles) < max_new:
            batch = await self._articles.find(
                ArticleFilter(
                    status=ArticleStatus.ACCEPTED,
                    limit=_BATCH_SIZE,
                    min_score=0.65,
                    offset=offset,
                    sort_by="created_at",
                    sort_dir="desc",
                ),
                user_id=snapshot.user_id,
            )

            if not batch:
                break  # Статті в базі закінчились

            for a in batch:
                # Нормалізуємо ID статті до UUID для коректного порівняння
                article_uuid = a.id if isinstance(a.id, UUID) else UUID(str(a.id))
                title_key = a.title.strip().lower() if a.title else ""

                if article_uuid not in existing_ids and title_key not in existing_titles:
                    new_articles.append(a)
                    existing_ids.add(article_uuid)
                    if title_key:
                        existing_titles.add(title_key)

                    if len(new_articles) >= max_new:
                        break

            offset += _BATCH_SIZE

            if offset > _MAX_OFFSET:
                logger.warning(
                    "Reached max offset %d for snapshot=%s, stopping.",
                    _MAX_OFFSET, snapshot.id,
                )
                break

        if not new_articles:
            return []

        ranked = self._rank(new_articles)
        next_rank = max((item.rank for item in snapshot.items), default=0) + 1

        return [
            self._make_item(snapshot.id, article, next_rank + i)
            for i, article in enumerate(ranked)
        ]

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _rank(articles: list) -> list:
        def _pub_ts(a) -> float:
            pub = getattr(a, "published_at", None)
            val = getattr(pub, "value", None) if pub else None
            return val.timestamp() if val else 0.0

        return sorted(articles, key=lambda a: -_pub_ts(a))

    @staticmethod
    def _make_item(snapshot_id: UUID, article, rank: int) -> FeedItem:
        def _pub_val(a) -> datetime | None:
            pub = getattr(a, "published_at", None)
            return getattr(pub, "value", None) if pub else None

        return FeedItem(
            id=uuid4(),
            snapshot_id=snapshot_id,
            article_id=article.id if isinstance(article.id, UUID) else UUID(str(article.id)),
            rank=rank,
            score=article.relevance_score or 0.0,
            language=article.language,
            status="unread",
            article_title=article.title,
            article_url=article.url,
            article_published_at=_pub_val(article),
        )

    def _to_view(self, snapshot: FeedSnapshot) -> FeedSnapshotView:
        return FeedSnapshotView(
            id=snapshot.id,
            user_id=snapshot.user_id,
            generated_at=snapshot.generated_at,
            items=[
                FeedItemView(
                    id=item.id,
                    article_id=item.article_id,
                    rank=item.rank,
                    score=item.score,
                    language=item.language,
                    status=item.status,
                    article_title=item.article_title,
                    article_url=item.article_url,
                    article_relevance_score=item.score,
                    article_published_at=item.article_published_at,
                )
                for item in snapshot.items
            ],
        )