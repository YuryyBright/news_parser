# application/use_cases/mark_article_read.py
"""
MarkArticleReadUseCase — позначити статтю як прочитану в активному feed snapshot.

Логіка:
  1. Знайти активний FeedItem для (user_id, article_id) через IFeedRepository
  2. Якщо не знайдено → повернути False (роутер → HTTP 404)
  3. Якщо вже read → idempotent, повернути True
  4. Оновити статус → "read"

DDD:
  ✅ залежить від IFeedRepository (порт з build_feed.py)
  ✅ повертає bool — роутер вирішує HTTP статус
  ✅ мутація через репозиторій, не через ORM напряму
"""
from __future__ import annotations

import logging
from uuid import UUID

from src.application.use_cases.build_feed import IFeedRepository

logger = logging.getLogger(__name__)


class MarkArticleReadUseCase:

    def __init__(self, feed_repo: IFeedRepository) -> None:
        self._feed = feed_repo

    async def execute(self, user_id: UUID, article_id: UUID) -> bool:
        """
        True  → item знайдено і позначено (або вже було read).
        False → активний item не знайдено.
        """
        item = await self._feed.find_active_item(user_id, article_id)
        if item is None:
            logger.info(
                "mark_read: no active feed item for user=%s article=%s",
                user_id, article_id,
            )
            return False

        if item.status == "read":
            logger.info(
                "mark_read: already read item=%s user=%s article=%s",
                item.id, user_id, article_id,
            )
            return True

        await self._feed.mark_item_read(item.id)
        logger.info(
            "Feed item marked read: item=%s user=%s article=%s",
            item.id, user_id, article_id,
        )
        return True
