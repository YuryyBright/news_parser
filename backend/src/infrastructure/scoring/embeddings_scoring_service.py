# infrastructure/scoring/embeddings_scoring_service.py
"""
EmbeddingsScoringService — другий шар scoring.

Алгоритм:
  1. Кодуємо текст статті → вектор (384-dim, multilingual-e5)
  2. Беремо центроїд профілю інтересів з ChromaDB
  3. Cosine similarity → score ∈ [0.0, 1.0]

Cold start (профіль порожній):
  Повертаємо COLD_START_SCORE = 0.55.
  Трохи вище threshold (0.25) → статті проходять і починають наповнювати профіль.
  Але не 1.0 → BM25 ще фільтрує явний мусор.

Важливо:
  Цей сервіс сам НЕ зберігає вектори у профіль.
  Це робить ProcessArticlesUseCase після scoring (implicit feedback).
  Розділення відповідальності: scoring ≠ learning.
"""
from __future__ import annotations

import logging

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.ml.embedder import Embedder
from src.infrastructure.vector_store.interest_profile_repo import InterestProfileRepository

logger = logging.getLogger(__name__)

# Score при cold start (порожній профіль)
# Досить щоб пройти threshold але не 1.0
COLD_START_SCORE = 0.55


class EmbeddingsScoringService(IScoringService):
    """
    Scoring через порівняння з профілем інтересів.

    Args:
        embedder:      Embedder.instance() — singleton моделі
        profile_repo:  InterestProfileRepository — читає центроїд з ChromaDB
    """

    def __init__(
        self,
        embedder: Embedder,
        profile_repo: InterestProfileRepository,
    ) -> None:
        self._embedder = embedder
        self._profile_repo = profile_repo

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        if not text or not text.strip():
            return 0.0

        # Беремо центроїд профілю
        centroid = await self._profile_repo.get_centroid()

        if centroid is None:
            # Cold start — профіль ще порожній
            logger.debug("EmbeddingsScoring: cold start, returning %.2f", COLD_START_SCORE)
            return COLD_START_SCORE

        # Кодуємо статтю
        article_vec = self._embedder.encode_passage(text)

        # Cosine similarity (обидва вектори L2-нормовані → dot product)
        similarity = self._embedder.cosine_similarity(article_vec, centroid)

        # Обрізаємо в [0, 1] — теоретично може бути від'ємним
        score = max(0.0, min(float(similarity), 1.0))

        logger.debug("EmbeddingsScoring: similarity=%.3f", score)
        return score

    async def encode(self, content: ParsedContent):
        """
        Публічний метод для отримання вектора статті.
        Використовується в ProcessArticlesUseCase для збереження у профіль.

        Returns: np.ndarray shape (384,) dtype=float32
        """
        return self._embedder.encode_passage(content.full_text())