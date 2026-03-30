# infrastructure/scoring/composite_scoring_service.py
"""
CompositeScoringService — двошаровий scoring.

Шар 1 — BM25 (pre-filter):
  Швидкий keyword-based filter.
  Якщо BM25 score < bm25_min_threshold → reject одразу (score=0.0).
  Стаття про котиків або рекламу не дістанеться до важкого embedding scoring.

Шар 2 — Embeddings (semantic scoring):
  Порівнює вектор статті з профілем інтересів.
  Дає семантичний score незалежно від мови.

Фінальний score:
  weighted_sum = bm25_weight * bm25_score + embed_weight * embed_score

Налаштування (всі параметри в DI container або settings):
  bm25_min_threshold: float = 0.05   # нижче — reject без embeddings
  bm25_weight:        float = 0.35   # вага BM25 у фінальному score
  embed_weight:       float = 0.65   # вага embeddings у фінальному score

Чому BM25_WEIGHT < EMBED_WEIGHT:
  BM25 — надійний детектор теми, але грубий (слова без контексту).
  Embeddings — розуміє семантику, але залежить від профілю.
  65/35 дає перевагу семантиці але BM25 ще впливає на результат.
"""
from __future__ import annotations

import logging

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)


class CompositeScoringService(IScoringService):
    """
    Реалізує IScoringService через комбінацію BM25 + Embeddings.

    ProcessArticlesUseCase не знає про цей клас — отримує IScoringService.
    Підключається через DI container.

    Приклад у container.py:
        composite = CompositeScoringService(
            bm25=BM25ScoringService(),
            embeddings=EmbeddingsScoringService(embedder, profile_repo),
        )
        use_case = ProcessArticlesUseCase(
            ...
            scoring_service=composite,
        )
    """

    def __init__(
        self,
        bm25: IScoringService,
        embeddings: IScoringService,
        bm25_min_threshold: float = 0.05,
        bm25_weight: float = 0.35,
        embed_weight: float = 0.65,
    ) -> None:
        self._bm25 = bm25
        self._embeddings = embeddings
        self._bm25_min_threshold = bm25_min_threshold
        self._bm25_weight = bm25_weight
        self._embed_weight = embed_weight

        # Перевіряємо що ваги в нормі (не обов'язково суммуються в 1.0)
        assert bm25_weight > 0 and embed_weight > 0, "Weights must be positive"

    async def score(self, content: ParsedContent) -> float:
        # ── Шар 1: BM25 pre-filter ────────────────────────────────────────────
        bm25_score = await self._bm25.score(content)

        if bm25_score < self._bm25_min_threshold:
            logger.debug(
                "CompositeScoring: BM25=%.3f < threshold=%.3f → reject",
                bm25_score, self._bm25_min_threshold,
            )
            return 0.0

        # ── Шар 2: Embeddings ─────────────────────────────────────────────────
        embed_score = await self._embeddings.score(content)

        # ── Фінальний зважений score ──────────────────────────────────────────
        final = self._bm25_weight * bm25_score + self._embed_weight * embed_score

        logger.debug(
            "CompositeScoring: BM25=%.3f embed=%.3f final=%.3f",
            bm25_score, embed_score, final,
        )
        return min(final, 1.0)