# application/use_cases/process_articles.py
"""
ProcessArticlesUseCase — обробляє pending RawArticle → Article.

Pipeline для кожної статті:
  1. Detect language           (через ILanguageDetector порт)
  2. Встановлюємо content.language перед scoring
     → BM25 і GeoFilter бачать мову для geo-penalty
  3. Score relevance           (через IScoringService порт)
     - CompositeScoringService: BM25+geo pre-filter + Embeddings + geo final
  4. Dedup check               (через DeduplicateRawArticleUseCase — MinHash + exact)
     - Exact duplicate (sha256): відкидаємо одразу
     - Near-duplicate (MinHash Jaccard): відкидаємо якщо similarity >= threshold
     - Унікальний: зберігаємо підпис для майбутніх перевірок
  5. Reject якщо score нижче threshold
  6. Build Article aggregate
  7. Auto-tag якщо accepted    (через ITagger порт → EmbeddingTagger gap-based)
  8. Save Article + mark RawArticle processed
  9. Implicit feedback: якщо accepted → зберегти вектор у профіль

Fallback: якщо dedup_uc=None — примітивна перевірка по URL/hash.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any
from uuid import uuid4, UUID

from sqlalchemy.exc import IntegrityError

from src.application.ports.language_detector import ILanguageDetector
from src.application.ports.scoring_service import IScoringService
from src.application.ports.tagger import ITagger
from src.application.ports.translator import ITranslator, TranslationError
from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.knowledge.entities import Article, Tag
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleStatus, ContentHash, PublishedAt
from src.domain.deduplication.services import DeduplicationDomainService

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


# ─── Порт для implicit feedback ──────────────────────────────────────────────

class IProfileLearner(ABC):
    @abstractmethod
    async def add_to_profile(
        self,
        article_id: UUID,
        content_text: str,
        score: float,
        tags: list[str],
    ) -> None: ...
    async def remove_from_profile(self, article_id: UUID, content_text: str = None) -> None: ...


# ─── DTO результату ───────────────────────────────────────────────────────────

@dataclass
class ProcessArticlesResult:
    processed: int = 0
    accepted:  int = 0
    rejected:  int = 0
    failed:    int = 0
    dedup_skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ─── Use Case ─────────────────────────────────────────────────────────────────

class ProcessArticlesUseCase:

    def __init__(
        self,
        session_factory: Callable[..., Any],
        raw_repo_factory: Callable[[Any], IRawArticleRepository],
        article_repo_factory: Callable[[Any], IArticleRepository],
        language_detector: ILanguageDetector,
        scoring_service: IScoringService,
        tagger: ITagger,
        profile_learner: IProfileLearner,
        dedup_uc=DeduplicationDomainService,
        batch_size: int = _BATCH_SIZE,
        threshold: float = 0.55,
        translator: ITranslator | None = None,
        target_language: str = "uk",
    ) -> None:
        self._session_factory      = session_factory
        self._raw_repo_factory     = raw_repo_factory
        self._article_repo_factory = article_repo_factory
        self._lang_detector        = language_detector
        self._scoring_service      = scoring_service
        self._tagger               = tagger
        self._profile_learner      = profile_learner
        if callable(dedup_uc) and not hasattr(dedup_uc, "execute"):
            self._dedup_uc_factory = dedup_uc
        else:
            self._dedup_uc_factory = (lambda uc: lambda _session: uc)(dedup_uc) if dedup_uc else None
        self._batch_size           = batch_size
        self._threshold            = threshold
        self._translator           = translator
        self._target_language      = target_language

    async def execute(self) -> ProcessArticlesResult:
        result = ProcessArticlesResult()

        async with self._session_factory() as session:
            async with session.begin():
                raw_repo = self._raw_repo_factory(session)
                raw_articles = await raw_repo.get_unprocessed(limit=self._batch_size)

        if not raw_articles:
            logger.debug("process_articles: no pending articles")
            return result

        logger.info("process_articles: processing %d articles", len(raw_articles))

        for raw in raw_articles:
            try:
                outcome = await self._run_one(raw)
                result.processed += 1
                if outcome == "accepted":
                    result.accepted += 1
                elif outcome == "dedup":
                    result.dedup_skipped += 1
                else:
                    result.rejected += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"raw_id={raw.id}: {exc}")
                logger.exception("Failed to process raw article %s", raw.id)

        logger.info(
            "process_articles done: processed=%d accepted=%d rejected=%d "
            "dedup_skipped=%d failed=%d",
            result.processed, result.accepted, result.rejected,
            result.dedup_skipped, result.failed,
        )
        return result

    async def _run_one(self, raw: RawArticle) -> str:
        """Повертає 'accepted' | 'rejected' | 'dedup'."""
        async with self._session_factory() as session:
            async with session.begin():
                return await self._process_one(session, raw)

    async def _process_one(self, session, raw: RawArticle) -> str:
        article_repo = self._article_repo_factory(session)
        raw_repo     = self._raw_repo_factory(session)

        # ── 1. Detect language ────────────────────────────────────────────────
        language = await self._detect_language(raw)

        # ── 2. Встановлюємо language в content перед scoring ─────────────────
        _inject_language(raw.content, language)

        # ── 3. Score (BM25+geo + Embeddings + geo final) ──────────────────────
        relevance_score = await self._score(raw)

        logger.info(
            "Article scored: url=%s lang=%s score=%.3f threshold=%.3f",
            raw.content.url, language, relevance_score, self._threshold,
        )

        # ── 4. Dedup ──────────────────────────────────────────────────────────
        dedup_uc = self._dedup_uc_factory(session) if self._dedup_uc_factory else None
        is_dup, dup_reason = await self._check_dedup(raw, article_repo, raw_repo, dedup_uc)
        if is_dup:
            logger.info(
                "Deduplicated: url=%s lang=%s score=%.3f reason=%s",
                raw.content.url, language, relevance_score, dup_reason,
            )
            await raw_repo.mark_processed(raw.id)
            return "dedup"

        # ── 5. Reject якщо score нижче threshold ──────────────────────────────
        if relevance_score < self._threshold:
            logger.info(
                "Rejected: url=%s lang=%s score=%.3f (< %.3f)",
                raw.content.url, language, relevance_score, self._threshold,
            )
            article = _build_article(raw, language)
            article.reject(relevance_score)
            await article_repo.save(article)
            await raw_repo.mark_processed(raw.id)
            return "rejected"

        # ── Зберігаємо оригінальний текст ДО перекладу ───────────────────────
        original_full_text = raw.content.full_text()

        # ── 5.5. Переклад (тільки для accepted статей) ────────────────────────
        original_title = raw.content.title
        original_body  = raw.content.body
        if self._translator is not None:
            language = await self._translate_content(raw, language)

        # ── 6. Тегування через EmbeddingTagger (gap-based) ───────────────────
        translated_full_text = raw.content.full_text()
        tag_names = self._tagger.tag(translated_full_text)

        # ── 7. Прийняти і зберегти ────────────────────────────────────────────
        article = _build_article(raw, language, original_title, original_body)
        article.accept(relevance_score)

        if tag_names:
            tags = [Tag(name=name, source="auto") for name in tag_names]
            article.add_tags(tags)

        try:
            await article_repo.save(article)
        except IntegrityError:
            # Race condition: інший конкурентний таск вже зберіг цю статтю
            # між нашим dedup-check і save. Трактуємо як дублікат.
            logger.info(
                "Race condition dedup: url=%s content_hash already exists",
                raw.content.url,
            )
            await raw_repo.mark_processed(raw.id)
            return "dedup"

        await raw_repo.mark_processed(raw.id)

        logger.info(
            "Accepted: raw_id=%s article=%s lang=%s score=%.3f tags=%s",
            raw.id, article.id, language, relevance_score, tag_names,
        )

        return "accepted"

    # ─── Dedup helpers ────────────────────────────────────────────────────────

    async def _check_dedup(
        self,
        raw: RawArticle,
        article_repo,
        raw_repo,
        dedup_uc=None,
    ) -> tuple[bool, str | None]:
        if dedup_uc is not None:
            return await self._check_dedup_minhash(raw, dedup_uc)
        return await self._check_dedup_primitive(raw, article_repo, raw_repo)

    async def _check_dedup_minhash(
        self,
        raw: RawArticle,
        dedup_uc,
    ) -> tuple[bool, str | None]:
        """MinHash деduplication через DeduplicateRawArticleUseCase."""
        try:
            result = await dedup_uc.execute(raw.id)
        except Exception as exc:
            logger.warning(
                "Dedup check failed for raw_id=%s, skipping dedup: %s",
                raw.id, exc,
            )
            return False, None

        if result.is_duplicate:
            sim_info = (
                f" similarity={result.similarity:.3f}"
                if result.similarity is not None
                else ""
            )
            logger.info(
                "Dedup reject: url=%s reason=%s existing=%s%s",
                raw.content.url, result.reason, result.existing_id, sim_info,
            )
            return True, str(result.reason)

        return False, None

    async def _check_dedup_primitive(
        self,
        raw: RawArticle,
        article_repo,
        raw_repo,
    ) -> tuple[bool, str | None]:
        """
        Fallback: примітивна дедуплікація по URL і hash.
        Використовується тільки якщо dedup_uc не підключений.
        """
        if await article_repo.get_by_url(raw.content.url):
            logger.debug("Duplicate url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return True, "exact_url"

        if await article_repo.exists_by_hash(raw.content_hash):
            logger.info("Duplicate hash url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return True, "exact_hash"

        return False, None

    # ─── Інші helpers ─────────────────────────────────────────────────────────

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

    async def _translate_content(self, raw: RawArticle, language: str) -> str:
        if not self._translator.should_translate(language, self._target_language):
            return language

        try:
            title_result = await self._translator.translate(
                raw.content.title or "",
                target_language=self._target_language,
                source_language=language if language != "unknown" else None,
            )
            body_result = await self._translator.translate(
                raw.content.body or "",
                target_language=self._target_language,
                source_language=language if language != "unknown" else None,
            )

            try:
                raw.content.title = title_result.text
            except (AttributeError, TypeError):
                object.__setattr__(raw.content, "title", title_result.text)

            try:
                raw.content.body = body_result.text
            except (AttributeError, TypeError):
                object.__setattr__(raw.content, "body", body_result.text)

            resolved_language = language
            if language == "unknown" and body_result.detected_language:
                resolved_language = body_result.detected_language
                _inject_language(raw.content, resolved_language)

            logger.info(
                "Translated: url=%s lang=%s→%s",
                raw.content.url, language, self._target_language,
            )
            return resolved_language

        except TranslationError as exc:
            logger.warning("Translation skipped for %s: %s", raw.content.url, exc)
            return language


# ─── Module-level helpers ─────────────────────────────────────────────────────

def _inject_language(content, language: str) -> None:
    try:
        existing = getattr(content, "language", None)
        if not existing:
            try:
                content.language = language
            except (AttributeError, TypeError):
                object.__setattr__(content, "language", language)
    except Exception as exc:
        logger.debug("Could not inject language into content: %s", exc)


def _build_article(
    raw: RawArticle,
    language: str,
    original_title: str | None = None,
    original_body: str | None = None,
) -> Article:
    return Article(
        id=uuid4(),
        source_id=raw.source_id,
        raw_article_id=str(raw.id),
        title=raw.content.title,
        body=raw.content.body,
        original_title=original_title,
        original_body=original_body,
        url=raw.content.url,
        language=language,
        status=ArticleStatus.PENDING,
        relevance_score=0.0,
        content_hash=ContentHash(value=raw.content_hash),
        published_at=PublishedAt(value=raw.content.published_at) if raw.content.published_at else None,
        tags=[],
    )