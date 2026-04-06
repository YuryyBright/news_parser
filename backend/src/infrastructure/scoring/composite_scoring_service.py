# infrastructure/scoring/composite_scoring_service.py
"""
CompositeScoringService — тришаровий scoring.

[ОНОВЛЕНО] Додано 3-й шар: GeoRelevanceFilter.

Шар 1 — BM25 (pre-filter з вбудованим geo_multiplier):
  Якщо bm25_score (вже з geo_mult) < bm25_min_threshold → reject одразу (score=0.0).
  BM25ScoringService сам застосовує geo_multiplier до свого score.
  Тому bm25_min_threshold тепер враховує обидва аспекти разом.

  Приклад:
    HU-стаття про NATO без HU контексту:
      bm25_raw=0.15, geo_mult=0.40 → bm25_adjusted=0.06
      0.06 >= bm25_min_threshold(0.05) → проходить, але вже "слабкий"

    HU-стаття "котики милі":
      bm25_raw=0.01, geo_mult=0.40 → bm25_adjusted=0.004
      0.004 < 0.05 → reject одразу

Шар 2 — Embeddings (semantic scoring):
  Порівнює вектор статті з профілем інтересів.
  Повертає cosine similarity без geo-корекції.

Шар 3 — Geo final multiplier:
  Застосовуємо geo_multiplier до ФІНАЛЬНОГО зваженого score.
  GeoRelevanceFilter.analyze() викликається повторно (дешево — regex).
  Це потрібно бо embeddings можуть "рятувати" тематично релевантні статті
  навіть якщо BM25 був слабким — і гео-фільтр має останнє слово.

  Приклад:
    HU-стаття про NATO (geo_mult=0.40):
      bm25=0.06 (adjusted), embed=0.70 (якщо профіль любить NATO)
      weighted = 0.35*0.06 + 0.65*0.70 = 0.021 + 0.455 = 0.476
      final = 0.476 * 0.40 = 0.190
      0.190 < threshold(0.25) → REJECT ✓ (саме те що хотіли)

    HU-стаття про Угорщину в NATO (geo_mult=1.0):
      bm25=0.15 (adjusted=0.15*1.0), embed=0.70
      weighted = 0.35*0.15 + 0.65*0.70 = 0.0525 + 0.455 = 0.507
      final = 0.507 * 1.0 = 0.507
      0.507 >= 0.25 → ACCEPT ✓

    HU-стаття про Закарпаття і мобілізацію (geo_mult=1.0):
      bm25=0.45, embed=0.80
      weighted = 0.35*0.45 + 0.65*0.80 = 0.1575 + 0.52 = 0.677
      final = 0.677 * 1.0 = 0.677 → ACCEPT ✓

Налаштування:
  bm25_min_threshold: float = 0.05   # після geo_mult корекції у BM25
  bm25_weight:        float = 0.35
  embed_weight:       float = 0.65
"""
from __future__ import annotations

import logging

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.scoring.geo_relevance_filter import GeoRelevanceFilter

logger = logging.getLogger(__name__)


class CompositeScoringService(IScoringService):
    """
    Реалізує IScoringService через BM25 + Embeddings + GeoFilter.

    ProcessArticlesUseCase не знає про цей клас — отримує IScoringService.

    ВАЖЛИВО: ParsedContent.language має бути заповнений до виклику score().
    ProcessArticlesUseCase викликає _detect_language() перед _score() — це правильно.

    Приклад у container.py:
        geo_filter = GeoRelevanceFilter()
        composite = CompositeScoringService(
            bm25=BM25ScoringService(geo_filter=geo_filter),
            embeddings=EmbeddingsScoringService(embedder, profile_repo),
            geo_filter=geo_filter,   # той самий інстанс — без дублювання
        )
    """

    def __init__(
        self,
        bm25: IScoringService,
        embeddings: IScoringService,
        geo_filter: GeoRelevanceFilter | None = None,
        bm25_min_threshold: float = 0.07,
        bm25_weight: float = 0.35,
        embed_weight: float = 0.65,
    ) -> None:
        self._bm25 = bm25
        self._embeddings = embeddings
        self._geo_filter = geo_filter or GeoRelevanceFilter()
        self._bm25_min_threshold = bm25_min_threshold
        self._bm25_weight = bm25_weight
        self._embed_weight = embed_weight

        assert bm25_weight > 0 and embed_weight > 0, "Weights must be positive"

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        language = getattr(content, "language", "") or ""

        # ── Шар 1: BM25 з вбудованим geo_multiplier ──────────────────────────
        # BM25ScoringService вже застосовує geo_mult до свого score.
        bm25_adjusted = await self._bm25.score(content)

        # if bm25_adjusted < self._bm25_min_threshold:
        #     logger.info(
        #         "CompositeSC: BM25_adjusted=%.3f < threshold=%.3f → early reject (lang=%s)",
        #         bm25_adjusted, self._bm25_min_threshold, language,
        #     )
        #     return 0.0

        # ── Шар 2: Embeddings (без geo — чиста семантика) ─────────────────────
        embed_score = await self._embeddings.score(content)

        # ── Зважений score ────────────────────────────────────────────────────
        weighted = self._bm25_weight * bm25_adjusted + self._embed_weight * embed_score

        # ── Шар 3: Geo final multiplier ───────────────────────────────────────
        # Повторний виклик дешевий (regex, без ML).
        # GeoFilter має "останнє слово" — навіть якщо embeddings дали 0.9,
        # глобальна стаття чужою мовою отримає penalty.
        geo_result = self._geo_filter.analyze(text, language)
        final = weighted * geo_result.multiplier

        logger.info(
            "CompositeSC: BM25_adj=%.3f embed=%.3f weighted=%.3f "
            "geo_mult=%.2f final=%.3f lang=%s geo_reason=%s",
            bm25_adjusted, embed_score, weighted,
            geo_result.multiplier, final, language, geo_result.reason,
        )

        return min(final, 1.0)