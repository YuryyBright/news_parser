# application/use_cases/process_articles.py
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Callable, Any
from uuid import uuid4

from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.entities import Article
from src.domain.knowledge.value_objects import ArticleStatus, ContentHash, Language, PublishedAt
from src.domain.knowledge.services import ArticleClassificationService

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100

@dataclass
class ProcessArticlesResult:
    processed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

class ProcessArticlesUseCase:
    def __init__(
        self,
        session_factory: Callable[..., Any], 
        raw_repo_factory: Callable[[Any], IRawArticleRepository], 
        article_repo_factory: Callable[[Any], IArticleRepository], 
        language_detector=None,
        scoring_service=None,
        batch_size: int = _BATCH_SIZE,
        threshold: float = 0.25,
    ) -> None:
        self._session_factory = session_factory
        self._raw_repo_factory = raw_repo_factory
        self._article_repo_factory = article_repo_factory
        self._lang_detector = language_detector
        self._scoring_service = scoring_service
        self._batch_size = batch_size
        self._threshold = threshold

    async def execute(self) -> ProcessArticlesResult:
        result = ProcessArticlesResult()

        # ── читаємо pending в окремій короткій транзакції ─────────────────
        async with self._session_factory() as session:
            async with session.begin():
                # Використовуємо фабрику замість прямого імпорту
                raw_repo = self._raw_repo_factory(session)
                raw_articles = await raw_repo.get_unprocessed(limit=self._batch_size)

        if not raw_articles:
            logger.debug("process_articles: no pending articles")
            return result

        logger.info("process_articles: processing %d articles", len(raw_articles))

        # ── кожна стаття — окрема транзакція ─────────────────────────────
        for raw in raw_articles:
            try:
                # Винесено логіку сесії в окремий блок
                async with self._session_factory() as session:
                    async with session.begin():
                        await self._process_one_in_session(session, raw)
                result.processed += 1
            except Exception as exc:
                result.failed += 1
                error_msg = f"raw_id={raw.id}: {exc}"
                result.errors.append(error_msg)
                logger.exception("Failed to process raw article %s: %s", raw.id, exc)

        logger.info(
            "process_articles done: processed=%d failed=%d",
            result.processed, result.failed,
        )
        return result

    async def _process_one_in_session(self, session, raw) -> None:
        # Ініціалізуємо репозиторії через передані фабрики
        article_repo = self._article_repo_factory(session)
        raw_repo = self._raw_repo_factory(session)

        # ── 1. Detect language ────────────────────────────────────────────
        language_str = raw.content.language
        if not language_str and self._lang_detector :
            try:
                language_str = await self._lang_detector.detect(raw.content.full_text())
            except Exception as exc:
                logger.warning("Language detection failed for %s: %s", raw.id, exc)
                language_str = "unknown"

        try:
            language = Language(language_str) if language_str else Language.UNKNOWN
        except ValueError:
            language = Language.UNKNOWN

        # ── 2. Score ──────────────────────────────────────────────────────
        relevance_score = 0.0
        if self._scoring_service:
            try:
                relevance_score = await self._scoring_service.score(raw.content)
            except Exception as exc:
                logger.warning("Scoring failed for %s: %s", raw.id, exc)

        # ── 3. Dedup ──────────────────────────────────────────────────────
        if await article_repo.get_by_url(raw.content.url):
            logger.debug("Duplicate url=%s, skipping", raw.content.url)
            await raw_repo.mark_processed(raw.id)
            return

        content_hash = raw.content_hash or hashlib.sha256(
            raw.content.full_text().encode()
        ).hexdigest()

        if await article_repo.get_by_hash(content_hash):
            logger.debug("Duplicate hash url=%s, skipping", raw.content.url)
            await raw_repo.mark_processed(raw.id)
            return

        # ── 4. Build Article ──────────────────────────────────────────────
        article = Article(
            id=uuid4(),
            source_id=raw.source_id,
            raw_article_id=raw.id,
            title=raw.content.title,
            body=raw.content.body,
            url=raw.content.url,
            language=language,
            status=ArticleStatus.PENDING,
            relevance_score=0.0,
            content_hash=ContentHash(value=content_hash),
            published_at=PublishedAt(value=raw.content.published_at) if raw.content.published_at else None,
            tags=[],
        )

        # ── 5. Accept / Reject + теги ─────────────────────────────────────
        if relevance_score >= self._threshold:
            article.accept(relevance_score)
            tags = ArticleClassificationService().extract_auto_tags(article)
            if tags:
                article.add_tags(tags)
        else:
            article.reject(relevance_score)

        # ── 6. Зберегти ───────────────────────────────────────────────────
        await article_repo.save(article)
        await raw_repo.mark_processed(raw.id)

        logger.debug(
            "Processed raw=%s → article=%s status=%s score=%.3f",
            raw.id, article.id, article.status.value, relevance_score,
        )