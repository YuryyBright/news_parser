# application/use_cases/process_articles.py
"""
ProcessArticlesUseCase — обробляє pending RawArticle → Article.

Pipeline для кожної статті:
  1. Detect language           (через ILanguageDetector порт)
  2. Score relevance           (через IScoringService порт)
     - CompositeScoringService: BM25 pre-filter + Embeddings semantic scoring
  3. Dedup check               (url + content_hash в article repo)
  4. Build Article aggregate
  5. Accept (score >= threshold) або Reject
  6. Auto-tag якщо accepted    (через ITagger порт → EmbeddingTagger zero-shot)
  7. Save Article + mark RawArticle processed
  8. [НОВИЙ] Implicit feedback: якщо accepted → зберегти вектор у профіль

Зміни відносно попередньої версії:
  + ITagger порт замінює ArticleClassificationService (dependency injection)
  + IProfileLearner порт для implicit feedback (зберігання у ChromaDB)
  + Логування score для діагностики
  - Прибрано пряму залежність на ArticleClassificationService з domain layer

Чого тут НЕ МАЄ:
  - Деталей BM25/embeddings (це IScoringService)
  - Деталей EmbeddingTagger (це ITagger)
  - Прямих імпортів sentence-transformers, chromadb тощо
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any
from uuid import uuid4, UUID

import numpy as np

from src.application.ports.language_detector import ILanguageDetector
from src.application.ports.scoring_service import IScoringService
from src.application.ports.tagger import ITagger
from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.knowledge.entities import Article, Tag
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleStatus, ContentHash, PublishedAt

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


# ─── Порт для implicit feedback ──────────────────────────────────────────────

class IProfileLearner(ABC):
    """
    Порт для зберігання вектора прийнятої статті у профіль інтересів.

    Реалізація: infrastructure/vector_store/interest_profile_repo.py
    ProcessArticlesUseCase не знає про ChromaDB або embeddings — тільки цей інтерфейс.
    """

    @abstractmethod
    async def add_to_profile(
        self,
        article_id: UUID,
        content_text: str,
        score: float,
        tags: list[str],
    ) -> None:
        """
        Зберегти вектор статті у профіль інтересів.

        Args:
            article_id:   UUID статті (для ідемпотентності)
            content_text: повний текст (title + body) для кодування
            score:        relevance score що призвів до accept
            tags:         теги статті (метадані у профілі)
        """
        ...


# ─── DTO результату ───────────────────────────────────────────────────────────

@dataclass
class ProcessArticlesResult:
    processed: int = 0
    accepted:  int = 0
    rejected:  int = 0
    failed:    int = 0
    errors: list[str] = field(default_factory=list)


# ─── Use Case ─────────────────────────────────────────────────────────────────

class ProcessArticlesUseCase:
    """
    Worker use case — кожна стаття в окремій транзакції.
    session_factory передається щоб use case сам контролював lifecycle.
    """

    def __init__(
        self,
        session_factory: Callable[..., Any],
        raw_repo_factory: Callable[[Any], IRawArticleRepository],
        article_repo_factory: Callable[[Any], IArticleRepository],
        language_detector: ILanguageDetector,
        scoring_service: IScoringService,          # CompositeScoringService
        tagger: ITagger,                           # EmbeddingTagger (НОВИЙ)
        profile_learner: IProfileLearner,          # implicit feedback (НОВИЙ)
        batch_size: int = _BATCH_SIZE,
        threshold: float = 0.25,
    ) -> None:
        self._session_factory    = session_factory
        self._raw_repo_factory   = raw_repo_factory
        self._article_repo_factory = article_repo_factory
        self._lang_detector      = language_detector
        self._scoring_service    = scoring_service
        self._tagger             = tagger
        self._profile_learner    = profile_learner
        self._batch_size         = batch_size
        self._threshold          = threshold

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
                accepted = await self._run_one(raw)
                result.processed += 1
                if accepted:
                    result.accepted += 1
                else:
                    result.rejected += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"raw_id={raw.id}: {exc}")
                logger.exception("Failed to process raw article %s", raw.id)

        logger.info(
            "process_articles done: processed=%d accepted=%d rejected=%d failed=%d",
            result.processed, result.accepted, result.rejected, result.failed,
        )
        return result

    async def _run_one(self, raw: RawArticle) -> bool:
        """Обгортка для ізоляції транзакції. Повертає True якщо accepted."""
        async with self._session_factory() as session:
            async with session.begin():
                return await self._process_one(session, raw)

    async def _process_one(self, session, raw: RawArticle) -> bool:
        """
        Обробка однієї статті.
        Returns: True = accepted, False = rejected/dedup.
        """
        article_repo = self._article_repo_factory(session)
        raw_repo     = self._raw_repo_factory(session)

        # ── 1. Detect language ────────────────────────────────────────────────
        language = await self._detect_language(raw)

        # ── 2. Score (BM25 + Embeddings) ──────────────────────────────────────
        relevance_score = await self._score(raw)

        # ── 3. Dedup ──────────────────────────────────────────────────────────
        if await article_repo.get_by_url(raw.content.url):
            logger.debug("Duplicate url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return False

        if await article_repo.get_by_hash(raw.content_hash):
            logger.debug("Duplicate hash url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return False

        # ── 4. Reject якщо score нижче threshold ──────────────────────────────
        if relevance_score < self._threshold:
            logger.debug(
                "Score %.3f < threshold %.3f, rejecting url=%s",
                relevance_score, self._threshold, raw.content.url,
            )
            article = _build_article(raw, language)
            article.reject(relevance_score)
            await article_repo.save(article)
            await raw_repo.mark_processed(raw.id)
            return False

        # ── 5. Тегування через EmbeddingTagger ───────────────────────────────
        full_text = raw.content.full_text()
        tag_names = self._tagger.tag(full_text)

        # ── 6. Прийняти і зберегти ────────────────────────────────────────────
        article = _build_article(raw, language)
        article.accept(relevance_score)

        if tag_names:
            tags = [Tag(name=name, source="auto") for name in tag_names]
            article.add_tags(tags)

        await article_repo.save(article)
        await raw_repo.mark_processed(raw.id)

        logger.info(
            "Accepted: raw_id=%s article=%s score=%.3f tags=%s",
            raw.id, article.id, relevance_score, tag_names,
        )

        # ── 7. Implicit feedback: зберегти вектор у профіль ──────────────────
        # Поза транзакцією БД — ChromaDB операція незалежна
        # Помилка тут не скасовує збереження статті
        try:
            await self._profile_learner.add_to_profile(
                article_id=article.id,
                content_text=full_text,
                score=relevance_score,
                tags=tag_names,
            )
        except Exception as exc:
            # Не критично — стаття вже збережена
            logger.warning(
                "Profile update failed for article=%s: %s", article.id, exc
            )

        return True

    # ─── Helpers ──────────────────────────────────────────────────────────────

    async def _detect_language(self, raw: RawArticle) -> str:
        language_str = raw.content.language
        if not language_str:
            try:
                language_str = await self._lang_detector.detect(raw.content.full_text())
            except Exception as exc:
                logger.warning("Language detection failed for %s: %s", raw.id, exc)
                language_str = "unknown"
        return language_str or "unknown"

    async def _score(self, raw: RawArticle) -> float:
        try:
            return await self._scoring_service.score(raw.content)
        except Exception as exc:
            logger.warning("Scoring failed for %s: %s", raw.id, exc)
            return 0.0


# ─── Builder ──────────────────────────────────────────────────────────────────

def _build_article(raw: RawArticle, language: str) -> Article:
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