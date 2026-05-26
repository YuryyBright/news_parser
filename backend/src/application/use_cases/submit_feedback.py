# application/use_cases/submit_feedback.py
"""
SubmitFeedbackUseCase — записати explicit feedback (like/dislike) від юзера.

Pipeline:
  1. Перевірити що стаття існує (ArticleNotFound → HTTP 404)
  2. Зберегти / оновити UserFeedback через IFeedbackRepository
  3. Знайти активний FeedItem і позначити як read (best-effort)
  4. [НОВЕ] Оновити профіль інтересів:
       liked=True  → add_to_profile(score=1.0)  — підсилити напрямок
       liked=False → remove_from_profile()        — прибрати вектор з центроїду

Чому explicit feedback важливий для профілю:
  Implicit feedback (стаття прийнята → вектор зберігається) дає сигнал
  "ця тема пройшла поріг", але не розрізняє "дуже цікаво" від "ледве пройшло".
  Explicit like підсилює вектор з score=1.0 (замість relevance_score ~0.3-0.5).
  Explicit dislike видаляє вектор — центроїд більше не тягнеться до цієї теми.

  Результат через ~10-20 feedback-ів:
    - liked статті → центроїд зсувається до їхніх тем
    - disliked статті → їхній вплив обнуляється
    - Наступний batch process_articles буде ближчим до реальних інтересів

IProfileLearner:
  Порт визначений у process_articles.py.
  ProfileLearner (infrastructure) реалізує обидва методи.
  SubmitFeedbackUseCase отримує його через DI → container.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.dtos.article_dto import SubmitFeedbackCommand
from src.application.use_cases.build_feed import IFeedRepository
from src.application.use_cases.process_articles import IProfileLearner
from src.domain.feed.entities import FeedItemRef
from src.domain.feed.repositories import IFeedbackRepository, UserFeedback
from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository

logger = logging.getLogger(__name__)


# ── Use Case ──────────────────────────────────────────────────────────────────

class SubmitFeedbackUseCase:
    """
    Записує лайк/дизлайк і оновлює профіль інтересів.

    Ідемпотентний: повторний feedback для тієї самої пари (user, article)
    оновлює попередній запис.

    Args:
        article_repo:    для перевірки існування і отримання тексту
        feedback_repo:   для збереження UserFeedback
        feed_repo:       для позначення item як read
        profile_learner: для оновлення профілю інтересів (може бути None —
                         тоді профіль не оновлюється, зворотна сумісність)
    """

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
    async def execute(self, cmd: SubmitFeedbackCommand) -> None:
        # ── 1. Стаття має існувати ────────────────────────────────────────────
        article = await self._articles.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        # ── 2. Зберегти / оновити feedback ───────────────────────────────────
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

        # ── 3. Позначити item як read (best-effort) ───────────────────────────
        try:
            item: FeedItemRef | None = await self._feed.find_active_item(
                cmd.user_id, cmd.article_id
            )
            if item is not None and item.status != "read":
                await self._feed.mark_item_read(item.id)
        except Exception as exc:
            logger.warning(
                "Failed to mark feed item read: user=%s article=%s: %s",
                cmd.user_id, cmd.article_id, exc,
            )

        # ── 4. Оновити профіль інтересів (best-effort) ────────────────────────
        if self._profile_learner is None:
            return

        try:
            content_text = _article_text(article)
            tag_names    = _article_tags(article)

            if cmd.liked:
                await self._profile_learner.add_to_profile(
                    article_id=cmd.article_id,
                    content_text=content_text,   # ← оригінал
                    score=1.0,
                    tags=tag_names,
                )
                logger.info("Profile updated (like): article=%s tags=%s", cmd.article_id, tag_names)
            else:
                # content_text тепер доступний (був NameError раніше)
                removed = await self._profile_learner.remove_from_profile(cmd.article_id, content_text)
                logger.info("Profile updated (dislike): article=%s removed=%s", cmd.article_id, removed)

        except Exception as exc:
            # Профіль — не критична операція. Feedback вже збережено.
            logger.warning(
                "Profile update failed after feedback: user=%s article=%s liked=%s: %s",
                cmd.user_id, cmd.article_id, cmd.liked, exc,
            )
        # ── 5. DynamicCorpusManager — BM25 Рівень 3 (best-effort) ───────────
        # submit_feedback.py — замінити крок 5 повністю

        if self._corpus_manager is not None:
            try:
                content_text = _article_text(article)  # original text (HU/SK/RO)
                
                # Детектуємо мову з оригінального тексту, НЕ з article.language
                # (article.language = мова перекладу = "uk")
                original_lang = _detect_text_language(content_text)
                
                if original_lang not in {"en", "hu", "sk", "ro"}:
                    logger.info(
                        "BM25 corpus update skipped: lang=%s not in supported set, article=%s",
                        original_lang, cmd.article_id,
                    )
                else:
                    bucket = "positive" if cmd.liked else "negative"
                    if existing and existing.liked != cmd.liked:
                        old_bucket = "positive" if existing.liked else "negative"
                        self._corpus_manager.remove_article_feedback(
                            content_text, old_bucket, original_lang,
                        )
                    rebuilt = self._corpus_manager.add_article_feedback(
                        article_id=str(cmd.article_id),
                        text=content_text,
                        bucket=bucket,
                        language=original_lang,
                    )
                    if rebuilt:
                        logger.info("BM25 corpus rebuilt: article=%s", cmd.article_id)
            except Exception as exc:
                logger.warning("DynamicCorpusManager update failed: article=%s: %s", cmd.article_id, exc)

# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Helpers ───────────────────────────────────────────────────────────────────
def _detect_text_language(text: str) -> str:
    """Детектує мову тексту через langdetect. Fallback → 'unknown'."""
    if not text or len(text) < 30:
        return "unknown"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"
def _article_text(article) -> str:
    """Оригінальний текст для embedding — НЕ переклад."""
    # Пріоритет: original_* → fallback на перекладений
    title = getattr(article, "original_title", None) or getattr(article, "title", None)
    body  = getattr(article, "original_body", None)  or getattr(article, "body", None)
    parts = [p for p in [title, body] if p]
    return "\n\n".join(parts)

def _article_tags(article) -> list[str]:
    """Витягує імена тегів зі статті."""
    raw_tags = getattr(article, "tags", []) or []
    return [t.name if hasattr(t, "name") else str(t) for t in raw_tags]