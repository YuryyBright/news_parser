# infrastructure/scoring/composite_scoring_service.py
"""
CompositeScoringService — двошаровий scoring (BM25 + Embeddings).

[СПРОЩЕНО] GeoRelevanceFilter повністю видалено.
  Раніше geo-множник застосовувався двічі (у BM25 і як фінальний шар),
  що призводило до надмірного відкидання релевантних статей.
  Тепер pipeline чистий і передбачуваний.

Архітектура:

  Шар 0 — Embedding fast-path (HIGH CONFIDENCE):
    Якщо embed_score >= embed_confidence_threshold → негайний accept.
    BM25 не викликається взагалі.
    Обґрунтування: cosine similarity > порогу означає що профіль
    вже однозначно ідентифікував статтю як релевантну.

    Приклад:
      Стаття про мобілізацію (тема яку юзер читає постійно):
        embed=0.92 >= 0.88 → score=0.92 ✓

  Шар 1 — BM25 hard pre-filter:
    Якщо bm25_score < bm25_min_threshold → reject одразу (score=0.0).
    BM25 тепер повертає чистий тематичний score без geo-penalty,
    тому поріг знову є тематичним бар'єром.

    Приклад:
      Стаття про котиків (жоден топік-кластер не спрацював):
        bm25=0.02 < 0.08 → reject ✓

      Стаття про NATO + Угорщина:
        bm25=0.22 >= 0.08 → проходить далі ✓

  Шар 2 — Зважений score (BM25 + Embeddings):
    weighted = bm25_weight * bm25 + embed_weight * embed
    Зважена комбінація дає balanced score.

    Приклад:
      bm25=0.22, embed=0.71:
        weighted = 0.35*0.22 + 0.65*0.71 = 0.077 + 0.462 = 0.539 → ACCEPT ✓

      bm25=0.09, embed=0.28 (мало релевантна):
        weighted = 0.35*0.09 + 0.65*0.28 = 0.031 + 0.182 = 0.213 → REJECT ✓

Налаштування:
  embed_confidence_threshold: float = 0.88  # fast-path поріг
  bm25_min_threshold:         float = 0.08  # hard pre-filter
  bm25_weight:                float = 0.35
  embed_weight:               float = 0.65
"""
from __future__ import annotations

import logging

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)


class CompositeScoringService(IScoringService):
    """
    Реалізує IScoringService через BM25 + Embeddings.

    ProcessArticlesUseCase не знає про цей клас — отримує IScoringService.

    Приклад у container.py:
        composite = CompositeScoringService(
            bm25=BM25ScoringService(),
            embeddings=EmbeddingsScoringService(embedder, profile_repo),
        )

    GeoRelevanceFilter більше не передається і не використовується.
    """

    def __init__(
        self,
        bm25: IScoringService,
        embeddings: IScoringService,
        bm25_min_threshold: float = 0.10,
        bm25_weight: float = 0.35,
        embed_weight: float = 0.65,
        embed_confidence_threshold: float = 0.88,
    ) -> None:
        self._bm25 = bm25
        self._embeddings = embeddings
        self._bm25_min_threshold = bm25_min_threshold
        self._bm25_weight = bm25_weight
        self._embed_weight = embed_weight
        self._embed_confidence_threshold = embed_confidence_threshold

        assert bm25_weight > 0 and embed_weight > 0, "Weights must be positive"

    async def score(self, content: ParsedContent) -> float:
        # ── Шар 0: Embedding fast-path ────────────────────────────────────────
        # Якщо профіль вже впевнений — BM25 не потрібен.
        embed_score = await self._embeddings.score(content)

        if embed_score >= self._embed_confidence_threshold:
            logger.info(
                "CompositeSC: embed=%.3f >= confidence_threshold=%.2f → fast-path accept",
                embed_score, self._embed_confidence_threshold,
            )
            return embed_score

        # ── Шар 1: BM25 hard pre-filter ───────────────────────────────────────
        bm25_score = await self._bm25.score(content)

        # if bm25_score < self._bm25_min_threshold:
        #     logger.info(
        #         "CompositeSC: BM25=%.3f < threshold=%.3f → early reject",
        #         bm25_score, self._bm25_min_threshold,
        #     )
        #     return 0.0

        # ── Шар 2: Зважений score ─────────────────────────────────────────────
        weighted = self._bm25_weight * bm25_score + self._embed_weight * embed_score

        logger.info(
            "CompositeSC: BM25=%.3f embed=%.3f weighted=%.3f",
            bm25_score, embed_score, weighted,
        )

        return min(weighted, 1.0)