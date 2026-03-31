# application/use_cases/submit_feedback.py
"""
SubmitFeedbackUseCase — записати explicit feedback (like/dislike) від юзера.

Pipeline:
  1. Перевірити що стаття існує (ArticleNotFound → HTTP 404)
  2. Зберегти / оновити UserFeedback через IFeedbackRepository
  3. Знайти активний FeedItem і позначити як read (не критично — у try/except)

DDD:
  ✅ IArticleRepository, IFeedbackRepository, IFeedRepository — порти
  ✅ FeedItemRef та IFeedRepository беруться з build_feed (єдине джерело правди)
  ✅ ArticleNotFound — доменний виняток → presentation → HTTP 404
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.dtos.article_dto import SubmitFeedbackCommand
from src.application.use_cases.build_feed import  IFeedRepository
from src.domain.feed.entities import FeedItemRef
from src.domain.feed.repositories import IFeedbackRepository, UserFeedback
from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository

logger = logging.getLogger(__name__)




# ── Use Case ──────────────────────────────────────────────────────────────────

class SubmitFeedbackUseCase:
    """
    Записує лайк/дизлайк. Ідемпотентний: повторний feedback для тієї самої
    пари (user, article) оновлює попередній запис.
    """

    def __init__(
        self,
        article_repo: IArticleRepository,
        feedback_repo: IFeedbackRepository,
        feed_repo: IFeedRepository,
    ) -> None:
        self._articles  = article_repo
        self._feedback  = feedback_repo
        self._feed      = feed_repo

    async def execute(self, cmd: SubmitFeedbackCommand) -> None:
        # 1. Стаття має існувати
        article = await self._articles.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        # 2. Зберегти / оновити feedback
        existing = await self._feedback.get_by_user_article(cmd.user_id, cmd.article_id)
        feedback = UserFeedback(
            id=existing.id if existing else uuid4(),
            user_id=cmd.user_id,
            article_id=cmd.article_id,
            liked=cmd.liked,
            created_at=datetime.now(timezone.utc),
        )
        await self._feedback.save(feedback)

        logger.info(
            "Feedback saved: user=%s article=%s liked=%s",
            cmd.user_id, cmd.article_id, cmd.liked,
        )

        # 3. Позначити item як read у активному snapshot (best-effort)
        try:
            item: FeedItemRef | None = await self._feed.find_active_item(
                cmd.user_id, cmd.article_id
            )
            if item is not None and item.status != "read":
                await self._feed.mark_item_read(item.id)
        except Exception as exc:
            logger.warning(
                "Failed to mark feed item read after feedback: user=%s article=%s: %s",
                cmd.user_id, cmd.article_id, exc,
            )
