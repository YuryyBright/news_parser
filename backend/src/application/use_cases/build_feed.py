# application/use_cases/build_feed.py
"""
BuildFeedUseCase — будує або повертає кешований персоналізований фід.

Логіка:
  1. Шукаємо свіжий активний FeedSnapshot для user_id
     (свіжий = created_at не старіший за TTL, за замовчуванням 30 хв)
  2. Якщо є → повертаємо кешований snapshot
  3. Якщо немає → будуємо новий:
       a. Беремо accepted статті з IArticleRepository
       b. Ранжуємо за relevance_score desc + published_at desc
       c. Зберігаємо FeedSnapshot + FeedItems через IFeedRepository
       d. Повертаємо FeedSnapshotView

DDD:
  ✅ IArticleRepository та IFeedRepository — порти
  ✅ FeedSnapshotView — application DTO, не domain entity
  ✅ TTL — конфіг-параметр
  ✅ ranker — чиста функція
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.domain.feed.entities import FeedSnapshot
from src.application.dtos.feed_dto import FeedItemView, FeedSnapshotView
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.feed.entities import FeedItem, FeedSnapshot
from src.domain.feed.repositories import IFeedRepository
from src.domain.knowledge.value_objects import ArticleStatus, ArticleFilter
logger = logging.getLogger(__name__)

_DEFAULT_TTL_MINUTES = 30
_DEFAULT_FEED_SIZE   = 50

class BuildFeedUseCase:

    def __init__(
        self,
        article_repo: IArticleRepository,
        feed_repo: IFeedRepository,
        ttl_minutes: int = _DEFAULT_TTL_MINUTES,
        feed_size: int = _DEFAULT_FEED_SIZE,  
    ) -> None:
        self._articles  = article_repo
        self._feed      = feed_repo
        self._ttl       = timedelta(minutes=ttl_minutes)
        self._feed_size = feed_size
    

    async def get_or_build(self, user_id: UUID) -> FeedSnapshotView:
        existing = await self._feed.get_active_snapshot(user_id)
        if existing is not None and self._is_fresh(existing):
            logger.debug("Feed cache hit: user=%s snapshot=%s", user_id, existing.id)
            return self._to_view(existing)

        logger.info("Building new feed snapshot: user=%s", user_id)

        snapshot = await self._build(user_id)
        await self._feed.save_snapshot(snapshot)
        return self._to_view(snapshot)
    
    def _is_fresh(self, snapshot: FeedSnapshot) -> bool:
        generate  = snapshot.generated_at
        if generate.tzinfo is None:
            generate = generate.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - generate) <= self._ttl


    async def _build(self, user_id: UUID) -> FeedSnapshot:
        articles = await self._articles.find(
            ArticleFilter(
                status=ArticleStatus.ACCEPTED,
                limit=self._feed_size,
                offset=0,
            )
        )

        def _pub_ts(a) -> float:
            pub = getattr(a, "published_at", None)
            val = getattr(pub, "value", None) if pub else None
            return val.timestamp() if val else 0.0

        ranked = sorted(
            articles,
            key=lambda a: (-(a.relevance_score or 0.0), -_pub_ts(a)),
        )

        def _pub_val(a) -> datetime | None:
            pub = getattr(a, "published_at", None)
            return getattr(pub, "value", None) if pub else None

        snapshot_id = uuid4()
        now = datetime.now(timezone.utc)
        items = [
            FeedItem(
                id=uuid4(),
                snapshot_id=snapshot_id,
                article_id=article.id,
                rank=rank,
                score=article.relevance_score or 0.0,
                status="unread",
                article_title=article.title,
                article_url=article.url,
                article_published_at=_pub_val(article),
            )
            for rank, article in enumerate(ranked, start=1)
        ]
        return FeedSnapshot(id=snapshot_id, user_id=user_id, generated_at=now, items=items)
    
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
                    status=item.status,
                    article_title=item.article_title,
                    article_url=item.article_url,
                    article_relevance_score=item.score,
                    article_published_at=item.article_published_at,
                )
                for item in snapshot.items
            ],
        )
