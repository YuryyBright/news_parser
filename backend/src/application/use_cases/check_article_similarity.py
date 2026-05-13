# application/use_cases/check_article_similarity.py
"""
Два use cases для перевірки схожості статей через API:

  CheckDuplicateUseCase  — перевіряє чи є дублікат (exact hash + MinHash)
                           для довільного тексту (без збереження в БД).

  FindSimilarArticlesUseCase — знаходить схожі статті через векторний пошук
                               по chunk_repo (той самий що verify в RAG CLI).

Обидва use cases НЕ змінюють стан БД — тільки читання.
Використовуються виключно з API (presentation layer).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from src.domain.deduplication.services import DeduplicationDomainService

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DTOs
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DuplicateCheckResult:
    is_duplicate: bool
    reason: str | None = None          # "exact_raw" | "exact_article" | "near_similar"
    existing_id: UUID | None = None    # UUID знайденого дубліката (якщо є)
    similarity: float | None = None    # для near_similar
    content_hash: str | None = None    # sha256 переданого тексту (для діагностики)


@dataclass(frozen=True)
class SimilarArticleItem:
    chunk_id: str
    text: str                          # текст чанку (фрагмент статті)
    score: float                       # cosine similarity
    source: str | None = None          # назва джерела / файлу якщо є в метаданих
    article_id: UUID | None = None     # UUID статті якщо є в метаданих


@dataclass
class FindSimilarResult:
    query_title: str
    items: list[SimilarArticleItem] = field(default_factory=list)
    total_found: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# CheckDuplicateUseCase
# ══════════════════════════════════════════════════════════════════════════════

class CheckDuplicateUseCase:
    """
    Перевіряє довільний текст на дублікат без збереження в БД.

    Рівні перевірки (в порядку виконання):
      1. Exact hash → raw_articles (exclude_id=None бо немає свого ID)
      2. Exact hash → articles
      3. Near-duplicate → MinHash

    На відміну від DeduplicateRawArticleUseCase:
      - НЕ змінює статус raw article
      - НЕ зберігає MinHash підпис
      - приймає title+body напряму (без raw_article_id)
    """

    def __init__(
        self,
        raw_repo,           # IRawArticleRepository
        article_repo,       # IArticleRepository
        minhash_repo,       # IMinHashRepository
        dedup_service: DeduplicationDomainService,
        minhash_threshold: float = 0.5,
    ) -> None:
        self._raw_repo     = raw_repo
        self._art_repo     = article_repo
        self._minhash_repo = minhash_repo
        self._svc          = dedup_service
        self._threshold    = minhash_threshold

    async def execute(self, title: str, body: str) -> DuplicateCheckResult:
        # ── 1. Exact hash ──────────────────────────────────────────────────────
        content_hash = self._svc.compute_hash(title, body)

        # Перевіряємо в raw_articles (exclude_id=None — шукаємо будь-який збіг)
        exists_in_raw = await self._raw_repo.exists_by_hash(
            content_hash.value,
            exclude_id=None,
        )
        if exists_in_raw:
            logger.info("check_duplicate: exact match in raw_articles hash=%s", content_hash.short())
            return DuplicateCheckResult(
                is_duplicate=True,
                reason="exact_raw",
                content_hash=content_hash.value,
            )

        # Перевіряємо в articles
        existing_article = await self._art_repo.get_by_hash(content_hash.value)
        if existing_article is not None:
            logger.info(
                "check_duplicate: exact match in articles id=%s hash=%s",
                existing_article.id, content_hash.short(),
            )
            return DuplicateCheckResult(
                is_duplicate=True,
                reason="exact_article",
                existing_id=existing_article.id,
                content_hash=content_hash.value,
            )

        # ── 2. Near-duplicate (MinHash) ────────────────────────────────────────
        signature = self._svc.compute_minhash(title, body)
        similar = await self._minhash_repo.find_similar(
            signature,
            threshold=self._threshold,
            limit=1,
        )
        if similar:
            existing_id, similarity = similar[0]
            logger.info(
                "check_duplicate: near-duplicate similar_to=%s similarity=%.3f",
                existing_id, similarity,
            )
            return DuplicateCheckResult(
                is_duplicate=True,
                reason="near_similar",
                existing_id=existing_id,
                similarity=similarity,
                content_hash=content_hash.value,
            )

        # ── 3. Унікальний ──────────────────────────────────────────────────────

        
        logger.debug("check_duplicate: unique hash=%s", content_hash.short())
        return DuplicateCheckResult(
            is_duplicate=False,
            content_hash=content_hash.value,
        )


# ══════════════════════════════════════════════════════════════════════════════
# FindSimilarArticlesUseCase
# ══════════════════════════════════════════════════════════════════════════════

class FindSimilarArticlesUseCase:
    """
    Знаходить схожі статті через векторний пошук по chunk_repo.

    Той самий механізм що VerifySearchUseCase у RAG CLI —
    encode_passage → query_similar → повернути топ-N результатів.

    chunk_repo містить чанки з вже збережених статей/документів,
    тому результати — це фрагменти реальних публікацій.
    """

    def __init__(
        self,
        embedder,       # будь-який embedder з методом encode_passage(text) → np.ndarray
        chunk_repo,     # IChunkVectorRepository з методом query_similar(vec, n_results, ...) → list
        default_top_n: int = 5,
    ) -> None:
        self._embedder  = embedder
        self._chunk_repo = chunk_repo
        self._default_top_n = default_top_n

    async def execute(
        self,
        title: str,
        body: str,
        top_n: int | None = None,
        language_filter: str | None = None,
    ) -> FindSimilarResult:
        top_n = top_n or self._default_top_n
        query_text = f"{title} {body}".strip()

        if not query_text:
            return FindSimilarResult(query_title=title)

        # Кодуємо запит тим самим способом що і при інгестації
        query_vec = self._embedder.encode_passage(query_text)

        try:
            raw_results = await self._chunk_repo.query_similar(
                query_vec,
                n_results=top_n,
                language_filter=language_filter,
            )
        except Exception as exc:
            logger.warning("FindSimilar: vector search failed: %s", exc)
            return FindSimilarResult(query_title=title)

        items = []
        for r in raw_results:
            # r — об'єкт з полями text, score, і опціонально metadata
            meta = getattr(r, "metadata", {}) or {}
            article_id = None
            raw_aid = meta.get("article_id")
            if raw_aid:
                try:
                    article_id = UUID(str(raw_aid))
                except ValueError:
                    pass

            items.append(SimilarArticleItem(
                chunk_id=str(getattr(r, "id", "")),
                text=r.text,
                score=float(r.score),
                source=meta.get("similarity_score") or meta.get("file_name"),
                article_id=article_id,
            ))

        return FindSimilarResult(
            query_title=title,
            items=items,
            total_found=len(items),
        )