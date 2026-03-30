# application/use_cases/process_articles.py
"""
ProcessArticlesUseCase — обробляє pending RawArticle → Article.

Pipeline для кожної статті:
  1. Detect language        (через ILanguageDetector порт)
  2. Score relevance        (через IScoringService порт)
  3. Dedup check            (url + content_hash в article repo)
  4. Build Article aggregate
  5. Accept (score >= threshold) або Reject
  6. Auto-tag якщо accepted
  7. Save Article + mark RawArticle processed

Чого тут НЕМАЄ:
  - langdetect import (це infrastructure)
  - hashlib (хеш береться з raw.content_hash — вже обчислений)
  - Article(id=uuid4()) без домену — Article будується тут але
    через domain value objects і state machine методи
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Any
from uuid import uuid4

from src.application.ports.language_detector import ILanguageDetector
from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.knowledge.entities import Article
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.services import ArticleClassificationService
from src.domain.knowledge.value_objects import ArticleStatus, ContentHash, PublishedAt

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


@dataclass
class ProcessArticlesResult:
    processed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ProcessArticlesUseCase:
    """
    Версія для worker'а — кожна стаття в окремій транзакції.
    session_factory передається щоб use case сам контролював lifecycle.
    """

    def __init__(
        self,
        session_factory: Callable[..., Any],
        raw_repo_factory: Callable[[Any], IRawArticleRepository],
        article_repo_factory: Callable[[Any], IArticleRepository],
        language_detector: ILanguageDetector,
        scoring_service: IScoringService,
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

        # Читаємо pending в окремій короткій транзакції
        async with self._session_factory() as session:
            async with session.begin():
                raw_repo = self._raw_repo_factory(session)
                raw_articles = await raw_repo.get_unprocessed(limit=self._batch_size)

        if not raw_articles:
            logger.debug("process_articles: no pending articles")
            return result

        logger.info("process_articles: processing %d articles", len(raw_articles))

        # Кожна стаття — окрема транзакція (ізоляція помилок)
        for raw in raw_articles:
            try:
                async with self._session_factory() as session:
                    async with session.begin():
                        await self._process_one(session, raw)
                result.processed += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"raw_id={raw.id}: {exc}")
                logger.exception("Failed to process raw article %s", raw.id)

        logger.info(
            "process_articles done: processed=%d failed=%d",
            result.processed, result.failed,
        )
        return result

    async def _process_one(self, session, raw: RawArticle) -> None:
        article_repo = self._article_repo_factory(session)
        raw_repo     = self._raw_repo_factory(session)

        # ── 1. Detect language ────────────────────────────────────────────────
        language = await self._detect_language(raw)

        # ── 2. Score ──────────────────────────────────────────────────────────
        relevance_score = await self._score(raw)


        # ── 3. Dedup (проти вже збережених Article) ───────────────────────────
        if await article_repo.get_by_url(raw.content.url):
            logger.debug("Duplicate url=%s, skipping", raw.content.url)
            # await raw_repo.mark_deduplicated(raw.id)
            return

        if await article_repo.get_by_hash(raw.content_hash):
            logger.debug("Duplicate hash url=%s, skipping", raw.content.url)
            # await raw_repo.mark_deduplicated(raw.id)
            return

        # ── 4. Відфільтрувати статті з низьким score до збереження ───────────
        # Статті нижче threshold одразу reject — не зберігаємо в knowledge domain
        # якщо хочемо зберігати всі (для статистики) — прибрати цей early return
        if relevance_score < self._threshold:
            logger.debug(
                "Score %.3f < threshold %.3f, rejecting url=%s",
                relevance_score, self._threshold, raw.content.url,
            )
            article = _build_article(raw, language)
            logger.info(
                    "Processed raw_article_id=%s → article=%s status=%s score=%.3f tags=%s",
                    article.raw_article_id, article.id, article.status.value,
                    relevance_score, [t.name for t in article.tags],
                )
            article.reject(relevance_score)
            await article_repo.save(article)
            # await raw_repo.mark_processed(raw.id)
            return

        # ── 5. Прийняти і тегувати ────────────────────────────────────────────
        article = _build_article(raw, language)
        article.accept(relevance_score)

        tags = ArticleClassificationService().extract_auto_tags(article)
        if tags:
            article.add_tags(tags)

        # ── 6. Зберегти ───────────────────────────────────────────────────────
        await article_repo.save(article)
        # await raw_repo.mark_processed(raw.id)



    async def _detect_language(self, raw: RawArticle):
        """Detect language через порт. Fallback → UNKNOWN."""
        language_str = raw.content.language
        if not language_str:
            try:
                language_str = await self._lang_detector.detect(raw.content.full_text())
            except Exception as exc:
                logger.warning("Language detection failed for %s: %s", raw.id, exc)
                language_str = "unknown"
        try:
            return language_str
        except ValueError:
            return "unknown"

    async def _score(self, raw: RawArticle) -> float:
        """Score через порт. Fallback → 0.0."""
        try:
            return await self._scoring_service.score(raw.content)
        except Exception as exc:
            logger.warning("Scoring failed for %s: %s", raw.id, exc)
            return 0.0


def _build_article(raw: RawArticle, language: str) -> Article:
    """
    Побудувати Article aggregate з RawArticle.
    ContentHash береться з raw.content_hash — вже обчислений у ParsedContent.
    """
    return Article(
        id=uuid4(),
        source_id=raw.source_id,
        raw_article_id=str(raw.id),
        title=raw.content.title,
        body=raw.content.body,
        url=raw.content.url,
        language=language,
        status=ArticleStatus.PENDING,
        relevance_score=0.0,
        content_hash=ContentHash(value=raw.content_hash),
        published_at=PublishedAt(value=raw.content.published_at) if raw.content.published_at else None,
        tags=[],
    )