# application/use_cases/verify_search.py
"""
VerifySearchUseCase — інструмент ручного тестування векторного пошуку.

Дозволяє перевірити якість embeddings і релевантність результатів:
  1. Embed запит
  2. Пошук в ChromaDB (без фільтрації по threshold)
  3. Повертає топ-N результатів з деталями (score, text, source, language)

Використання:
  - CLI скрипт: python verify_search.py --query "Зеленський виступив" --top 10
  - REST ендпоінт: GET /rag/verify?q=...&top=10
  - Jupyter notebook: для дослідження якості retrieval

НЕ фільтрує по threshold — показує ВСЕ щоб можна було налаштувати поріг.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.application.ports.rag_ports import IChunkVectorRepository, IEmbeddingService
from src.domain.news_generation.entities import SearchResult
from src.domain.news_generation.prompts import SIMILARITY_THRESHOLD, MIN_TEXT_LENGTH

logger = logging.getLogger(__name__)


@dataclass
class VerifySearchResult:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_in_db: int = 0
    # Скільки з результатів пройшли б threshold генерації
    would_pass_filter: int = 0

    def print_report(self) -> None:
        """Виводить читабельний звіт у stdout."""
        print(f"\n{'='*60}")
        print(f"Query: {self.query!r}")
        print(f"Total chunks in DB: {self.total_in_db}")
        print(f"Results returned: {len(self.results)}")
        print(f"Would pass generation filter: {self.would_pass_filter}")
        print(f"  (threshold={SIMILARITY_THRESHOLD}, min_length={MIN_TEXT_LENGTH})")
        print(f"{'='*60}\n")

        for i, r in enumerate(self.results, 1):
            would_pass = (
                r.similarity_score >= SIMILARITY_THRESHOLD
                and len(r.text) > MIN_TEXT_LENGTH
            )
            status = "✅ PASS" if would_pass else "❌ SKIP"

            print(f"[{i}] {status}  score={r.similarity_score:.4f}  lang={r.language}")
            print(f"    source: {r.source}")
            print(f"    length: {len(r.text)} chars")
            print(f"    text:   {r.text}")
            print()


class VerifySearchUseCase:
    """
    Семантичний пошук для ручної верифікації якості retrieval.

    Повертає результати БЕЗ фільтрації — щоб можна було
    бачити всі кандидати і вирішити чи підходить threshold.
    """

    def __init__(
        self,
        embedder: IEmbeddingService,
        chunk_repo: IChunkVectorRepository,
        top_n: int = 10,
    ) -> None:
        self._embedder = embedder
        self._repo     = chunk_repo
        self._top_n    = top_n

    async def execute(
        self,
        query: str,
        top_n: int | None = None,
        language_filter: str | None = None,
    ) -> VerifySearchResult:
        n = top_n or self._top_n

        logger.info("[verify] Query: %r  top_n=%d  lang=%s", query, n, language_filter)

        # 1. Embed
        query_vector = await self._embedder.embed_one(query)

        # 2. Кількість чанків у БД (для контексту)
        total = await self._repo.count()

        # 3. Пошук без фільтрації threshold
        results = await self._repo.query_similar(
            query_vector=query_vector,
            n_results=n,
            language_filter=language_filter,
        )

        logger.info("[verify] Returned %d results (total in DB: %d)", len(results), total)
        for r in results:
            logger.debug(
                "[verify]   score=%.4f  lang=%s  len=%d  source=%s",
                r.similarity_score, r.language, len(r.text), r.source,
            )

        # Підраховуємо скільки пройшли б фільтр
        would_pass = sum(
            1 for r in results
            if r.similarity_score >= SIMILARITY_THRESHOLD
            and len(r.text) > MIN_TEXT_LENGTH
        )

        return VerifySearchResult(
            query=query,
            results=results,
            total_in_db=total,
            would_pass_filter=would_pass,
        )