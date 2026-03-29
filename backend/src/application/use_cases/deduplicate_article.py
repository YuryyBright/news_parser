# application/use_cases/deduplicate_article.py
"""
DeduplicateRawArticleUseCase — перевіряє чи є raw article дублікатом.

Два рівні перевірки (в порядку виконання):

  1. EXACT duplicate (sha256)
     - Перевіряємо hash в raw_articles (раніше отриманий той самий URL)
     - Перевіряємо hash в articles (вже пройшов pipeline)
     → DuplicateContentError → raw.status = "deduplicated"

  2. NEAR-DUPLICATE (MinHash Jaccard)
     - Шукаємо схожі підписи в IMinHashRepository
     - Якщо similarity >= threshold → NearDuplicateContentError
     → raw.status = "deduplicated"

  3. PASS → зберігаємо MinHash підпис для майбутніх перевірок
     → raw.status без змін (залишається "pending")
     → pipeline продовжується далі (filter → article)

Результат:
  DeduplicationResult з полями is_duplicate, reason, existing_id

Use case НЕ створює Article — це наступний крок pipeline.
Use case НЕ знає про HTTP.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from src.domain.ingestion.dedup_service import DeduplicationDomainService
from src.domain.ingestion.exceptions import (
    DuplicateContentError,
    InvalidContentError,
    NearDuplicateContentError,
)
from src.domain.ingestion.repositories import IMinHashRepository, IRawArticleRepository
from src.domain.knowledge.repositories import IArticleRepository

logger = logging.getLogger(__name__)


# ── Result ────────────────────────────────────────────────────────────────────

class DuplicateReason(StrEnum):
    EXACT_RAW     = "exact_raw"      # вже є в raw_articles
    EXACT_ARTICLE = "exact_article"  # вже є в articles
    NEAR_SIMILAR  = "near_similar"   # MinHash similarity > threshold
    INVALID       = "invalid"        # не пройшов валідацію


@dataclass(frozen=True)
class DeduplicationResult:
    raw_article_id: UUID
    is_duplicate: bool
    reason: DuplicateReason | None = None
    existing_id: UUID | None = None
    similarity: float | None = None     # тільки для near-duplicate
    error_message: str | None = None    # тільки для invalid


# ── Use Case ──────────────────────────────────────────────────────────────────

class DeduplicateRawArticleUseCase:

    def __init__(
        self,
        raw_repo: IRawArticleRepository,
        article_repo: IArticleRepository,
        minhash_repo: IMinHashRepository,
        dedup_service: DeduplicationDomainService,
        minhash_threshold: float = 0.85,
    ) -> None:
        self._raw_repo    = raw_repo
        self._art_repo    = article_repo
        self._minhash_repo = minhash_repo
        self._svc         = dedup_service
        self._threshold   = minhash_threshold

    async def execute(self, raw_article_id: UUID) -> DeduplicationResult:
        # ── 0. Завантажити raw article ────────────────────────────────────────
        raw = await self._raw_repo.get(raw_article_id)
        if raw is None:
            raise ValueError(f"RawArticle not found: {raw_article_id}")

        title = raw.content.title
        body  = raw.content.body

        # ── 1. Валідація мінімального контенту ───────────────────────────────
        try:
            self._svc.validate_content(title, body)
        except InvalidContentError as exc:
            await self._raw_repo.mark_as_invalid(raw_article_id, exc.reason)
            logger.warning("Invalid content raw=%s: %s", raw_article_id, exc.reason)
            return DeduplicationResult(
                raw_article_id=raw_article_id,
                is_duplicate=True,
                reason=DuplicateReason.INVALID,
                error_message=exc.reason,
            )

        # ── 2. Exact duplicate — перевірити в raw_articles ────────────────────
        content_hash = self._svc.compute_hash(title, body)

        existing_raw = await self._raw_repo.get_by_hash(content_hash)
        if existing_raw is not None and existing_raw.id != raw_article_id:
            await self._raw_repo.mark_as_deduplicated(raw_article_id, existing_raw.id)
            logger.info(
                "Exact duplicate (raw): raw=%s duplicates=%s hash=%s",
                raw_article_id, existing_raw.id, content_hash.short(),
            )
            return DeduplicationResult(
                raw_article_id=raw_article_id,
                is_duplicate=True,
                reason=DuplicateReason.EXACT_RAW,
                existing_id=existing_raw.id,
            )

        # ── 3. Exact duplicate — перевірити в articles ────────────────────────
        existing_article = await self._art_repo.get_by_hash(content_hash.value)
        if existing_article is not None:
            await self._raw_repo.mark_as_deduplicated(raw_article_id, existing_article.id)
            logger.info(
                "Exact duplicate (article): raw=%s duplicates=%s hash=%s",
                raw_article_id, existing_article.id, content_hash.short(),
            )
            return DeduplicationResult(
                raw_article_id=raw_article_id,
                is_duplicate=True,
                reason=DuplicateReason.EXACT_ARTICLE,
                existing_id=existing_article.id,
            )

        # ── 4. Near-duplicate (MinHash) ───────────────────────────────────────
        signature = self._svc.compute_minhash(title, body)
        similar = await self._minhash_repo.find_similar(
            signature,
            threshold=self._threshold,
            limit=1,
        )

        if similar:
            existing_id, similarity = similar[0]
            await self._raw_repo.mark_as_deduplicated(raw_article_id, existing_id)
            logger.info(
                "Near-duplicate: raw=%s similar_to=%s similarity=%.3f threshold=%.2f",
                raw_article_id, existing_id, similarity, self._threshold,
            )
            return DeduplicationResult(
                raw_article_id=raw_article_id,
                is_duplicate=True,
                reason=DuplicateReason.NEAR_SIMILAR,
                existing_id=existing_id,
                similarity=similarity,
            )

        # ── 5. Унікальний — зберегти підпис для майбутніх перевірок ──────────
        await self._minhash_repo.save(raw_article_id, signature)
        logger.debug("Unique content: raw=%s hash=%s", raw_article_id, content_hash.short())

        return DeduplicationResult(
            raw_article_id=raw_article_id,
            is_duplicate=False,
        )


# ── Batch variant ─────────────────────────────────────────────────────────────

@dataclass
class BatchDeduplicationResult:
    unique:     list[UUID] = field(default_factory=list)
    duplicates: list[DeduplicationResult] = field(default_factory=list)
    errors:     list[tuple[UUID, str]] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        return {
            "unique": len(self.unique),
            "duplicates": len(self.duplicates),
            "errors": len(self.errors),
            "duplicate_reasons": _count_reasons(self.duplicates),
        }


class BatchDeduplicateUseCase:
    """
    Обробляє список pending raw articles.
    Кожна стаття — окрема транзакція.
    """

    def __init__(self, single_uc: DeduplicateRawArticleUseCase) -> None:
        self._uc = single_uc

    async def execute(self, raw_ids: list[UUID]) -> BatchDeduplicationResult:
        result = BatchDeduplicationResult()

        for raw_id in raw_ids:
            try:
                r = await self._uc.execute(raw_id)
                if r.is_duplicate:
                    result.duplicates.append(r)
                else:
                    result.unique.append(raw_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Dedup error for raw=%s: %s", raw_id, exc)
                result.errors.append((raw_id, str(exc)))

        logger.info("Batch dedup complete: %s", result.stats)
        return result


def _count_reasons(duplicates: list[DeduplicationResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in duplicates:
        key = d.reason.value if d.reason else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts
