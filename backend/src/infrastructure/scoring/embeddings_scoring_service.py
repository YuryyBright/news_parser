# infrastructure/scoring/embeddings_scoring_service.py
"""
EmbeddingsScoringService — другий шар scoring у CompositeScoringService.

Місце у пайплайні (див. composite_scoring_service.py):
  Шар 1: BM25ScoringService      (pre-filter + geo early-penalty)
  Шар 2: EmbeddingsScoringService ← ЦЕЙ ФАЙЛ
  Шар 3: geo final multiplier     (у Composite, повторний виклик GeoFilter)

Алгоритм:
  1. content.full_text() → кодуємо через Embedder.encode_passage()
  2. InterestProfileRepository.get_centroid() → вектор "смаку" з ChromaDB
  3. cosine_similarity(article_vec, centroid) → score ∈ [0.0, 1.0]

Cold start (профіль порожній, centroid is None):
  Повертаємо COLD_START_SCORE = 0.55.
  Обґрунтування:
    - Вище threshold (0.25) → статті проходять і наповнюють профіль
    - Нижче 1.0 → BM25 все ще відсіює явний сміттєвий контент
    - Після ~20-30 прийнятих статей профіль стає репрезентативним

Розподіл відповідальності:
  ✅ Цей клас: читає профіль, рахує similarity, повертає score
  ❌ Цей клас НЕ зберігає вектори у профіль
     Збереження — відповідальність ProfileLearner (implicit feedback),
     який викликається з ProcessArticlesUseCase ПІСЛЯ scoring.

Залежності (всі передаються через DI у container.py):
  Embedder              — singleton моделі multilingual-e5-small (384-dim)
  InterestProfileRepository — ChromaDB колекція з векторами "цікавих" статей

Підключення у container.py:
    embed_service = EmbeddingsScoringService(
        embedder=embedder,
        profile_repo=profile_repo,
    )
    composite = CompositeScoringService(
        bm25=bm25_service,
        embeddings=embed_service,
        ...
    )
"""
from __future__ import annotations

import logging

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.ml.embedder import Embedder
from src.infrastructure.vector_store.interest_profile_repo import InterestProfileRepository

logger = logging.getLogger(__name__)

# Score при cold start (порожній профіль — перші запуски системи)
# Трохи вище threshold(0.25) але не 1.0 → BM25 ще фільтрує сміттєвий контент.
COLD_START_SCORE = 0.55


class EmbeddingsScoringService(IScoringService):
    """
    Scoring через семантичне порівняння з профілем інтересів.

    Args:
        embedder:     Embedder.instance() — singleton завантаженої моделі.
        profile_repo: InterestProfileRepository — читає центроїд з ChromaDB.

    Note:
        ParsedContent.language НЕ використовується цим сервісом —
        гео-корекція відбувається у BM25 (шар 1) і Composite (шар 3).
        Цей сервіс повертає чисту семантичну схожість без гео-penalty.
    """

    def __init__(
        self,
        embedder: Embedder,
        profile_repo: InterestProfileRepository,
    ) -> None:
        self._embedder = embedder
        self._profile_repo = profile_repo

    async def score(self, content: ParsedContent) -> float:
        """
        Повертає cosine similarity між статтею і профілем інтересів.

        Returns:
            float ∈ [0.0, 1.0]:
              - COLD_START_SCORE (0.55) якщо профіль порожній
              - cosine similarity із центроїдом профілю інакше
        """
        text = content.full_text()
        if not text or not text.strip():
            logger.debug("EmbeddingsScoring: empty text → 0.0")
            return 0.0

        centroid = await self._profile_repo.get_centroid()

        if centroid is None:
            logger.debug(
                "EmbeddingsScoring: cold start (empty profile) → %.2f", COLD_START_SCORE
            )
            return COLD_START_SCORE

        article_vec = self._embedder.encode_passage(text)

        # Обидва вектори L2-нормовані (Embedder.encode_passage + InterestProfileRepository.get_centroid)
        # → cosine similarity = dot product
        similarity = self._embedder.cosine_similarity(article_vec, centroid)

        # Теоретично cosine може бути від'ємним → обрізаємо знизу
        score = float(np.clip(similarity, 0.0, 1.0))

        logger.debug(
            "EmbeddingsScoring: similarity=%.3f profile_size=?", score
        )
        return score

    async def encode(self, content: ParsedContent) -> np.ndarray:
        """
        Повертає вектор статті (384-dim, float32).

        Використовується у ProfileLearner для збереження у профіль
        і у майбутніх use cases для пошуку схожих статей.

        Returns:
            np.ndarray shape (384,) dtype=float32, L2-нормований.
        """
        text = content.full_text()
        return self._embedder.encode_passage(text)