# application/use_cases/submit_feedback.py
"""
SubmitFeedbackUseCase — записати explicit feedback (like/dislike) від юзера.

Pipeline:
  1. Перевірити що стаття існує (ArticleNotFound → HTTP 404)
  2. Якщо той самий feedback вже є → ВИДАЛИТИ (toggle off) → return {"action": "removed"}
  3. Зберегти / оновити UserFeedback → return {"action": "added" | "changed"}
  4. Знайти активний FeedItem і позначити як read (best-effort)
  5. Оновити профіль інтересів
  6. Оновити DynamicCorpusManager (BM25)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.application.dtos.article_dto import SubmitFeedbackCommand
from src.application.use_cases.build_feed import IFeedRepository
from src.application.use_cases.process_articles import IProfileLearner
from src.domain.feed.entities import FeedItemRef
from src.domain.feed.repositories import IFeedbackRepository, UserFeedback
from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository

logger = logging.getLogger(__name__)


class SubmitFeedbackUseCase:
    def __init__(
        self,
        article_repo: IArticleRepository,
        feedback_repo: IFeedbackRepository,
        feed_repo: IFeedRepository,
        profile_learner: IProfileLearner | None = None,
        corpus_manager=None,
    ) -> None:
        self._articles        = article_repo
        self._feedback        = feedback_repo
        self._feed            = feed_repo
        self._profile_learner = profile_learner
        self._corpus_manager  = corpus_manager

    async def execute(self, cmd: SubmitFeedbackCommand) -> dict:
        """
        Returns:
            {"action": "added"|"changed"|"removed", "liked": bool|None}
            "removed" — feedback скасовано (повторний клік на ту саму кнопку)
        """
        # ── 1. Стаття має існувати ────────────────────────────────────────────
        article = await self._articles.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        existing = await self._feedback.get_by_user_article(cmd.user_id, cmd.article_id)

        # ── 2. Toggle: той самий liked → видалити ─────────────────────────────
        if existing is not None and existing.liked == cmd.liked:
            await self._feedback.delete(existing.id)
            logger.info(
                "Feedback removed (toggle off): user=%s article=%s liked=%s",
                cmd.user_id, cmd.article_id, cmd.liked,
            )
            await self._undo_profile(article, cmd, existing)
            await self._undo_corpus(article, cmd, existing)
            return {"action": "removed", "liked": None}

        # ── 3. Зберегти / оновити feedback ───────────────────────────────────
        action = "changed" if existing is not None else "added"
        feedback = UserFeedback(
            id=existing.id if existing else uuid4(),
            user_id=cmd.user_id,
            article_id=cmd.article_id,
            liked=cmd.liked,
            created_at=datetime.now(timezone.utc),
        )
        await self._feedback.save(feedback)
        logger.info(
            "Feedback %s: user=%s article=%s liked=%s",
            action, cmd.user_id, cmd.article_id, cmd.liked,
        )

        # ── 4. Позначити item як read (best-effort) ───────────────────────────
        # try:
        #     item: FeedItemRef | None = await self._feed.find_active_item(
        #         cmd.user_id, cmd.article_id
        #     )
        #     if item is not None and item.status != "read":
        #         await self._feed.mark_item_read(item.id)
        # except Exception as exc:
        #     logger.warning(
        #         "Failed to mark feed item read: user=%s article=%s: %s",
        #         cmd.user_id, cmd.article_id, exc,
        #     )

        # ── 5. Оновити профіль інтересів (best-effort) ────────────────────────
        if self._profile_learner is not None:
            try:
                content_text = _article_text(article)
                tag_names    = _article_tags(article)

                # Якщо змінили оцінку (was like → now dislike або навпаки)
                if existing is not None and existing.liked != cmd.liked:
                    await self._profile_learner.remove_from_profile(
                        cmd.article_id, content_text
                    )

                if cmd.liked:
                    await self._profile_learner.add_to_profile(
                        article_id=cmd.article_id,
                        content_text=content_text,
                        score=1.0,
                        tags=tag_names,
                    )
                    logger.info("Profile updated (like): article=%s", cmd.article_id)
                else:
                    removed = await self._profile_learner.remove_from_profile(
                        cmd.article_id, content_text
                    )
                    logger.info("Profile updated (dislike): article=%s removed=%s", cmd.article_id, removed)

            except Exception as exc:
                logger.warning(
                    "Profile update failed: user=%s article=%s liked=%s: %s",
                    cmd.user_id, cmd.article_id, cmd.liked, exc,
                )

        # ── 6. DynamicCorpusManager (best-effort) ─────────────────────────────
        await self._update_corpus(article, cmd, existing)

        return {"action": action, "liked": cmd.liked}

    # ── Profile undo (toggle off) ─────────────────────────────────────────────

    async def _undo_profile(self, article, cmd, existing) -> None:
        if self._profile_learner is None:
            return
        try:
            content_text = _article_text(article)
            await self._profile_learner.remove_from_profile(cmd.article_id, content_text)
        except Exception as exc:
            logger.warning("Profile undo failed: article=%s: %s", cmd.article_id, exc)

    # ── Corpus helpers ────────────────────────────────────────────────────────

    async def _undo_corpus(self, article, cmd, existing) -> None:
        if self._corpus_manager is None:
            return
        try:
            content_text  = _article_text(article)
            original_lang = _detect_text_language(content_text)
            if original_lang not in {"en", "hu", "sk", "ro", 'pl'}:
                return
            old_bucket = "positive" if existing.liked else "negative"
            await self._corpus_manager.remove_article_feedback(
                content_text, old_bucket, original_lang
            )
        except Exception as exc:
            logger.warning("Corpus undo failed: article=%s: %s", cmd.article_id, exc)

    async def _update_corpus(self, article, cmd, existing) -> None:
        if self._corpus_manager is None:
            return
        try:
            content_text  = _article_text(article)
            original_lang = _detect_text_language(content_text)
            if original_lang not in {"en", "hu", "sk", "ro"}:
                logger.info(
                    "BM25 corpus update skipped: lang=%s, article=%s",
                    original_lang, cmd.article_id,
                )
                return

            bucket = "positive" if cmd.liked else "negative"

            # Якщо змінили оцінку — прибрати стару
            if existing is not None and existing.liked != cmd.liked:
                old_bucket = "positive" if existing.liked else "negative"
                await self._corpus_manager.remove_article_feedback(
                    content_text, old_bucket, original_lang,
                )

            rebuilt = await self._corpus_manager.add_article_feedback(
                article_id=str(cmd.article_id),
                text=content_text,
                bucket=bucket,
                language=original_lang,
            )
            if rebuilt:
                logger.info("BM25 corpus rebuilt: article=%s", cmd.article_id)

        except Exception as exc:
            logger.warning(
                "DynamicCorpusManager update failed: article=%s: %s",
                cmd.article_id, exc,
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_text_language(text: str) -> str:
    if not text or len(text) < 30:
        return "unknown"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"


def _article_text(article) -> str:
    title = getattr(article, "original_title", None) or getattr(article, "title", None)
    body  = getattr(article, "original_body",  None) or getattr(article, "body",  None)
    return "\n\n".join(p for p in [title, body] if p)


def _article_tags(article) -> list[str]:
    raw_tags = getattr(article, "tags", []) or []
    return [t.name if hasattr(t, "name") else str(t) for t in raw_tags]