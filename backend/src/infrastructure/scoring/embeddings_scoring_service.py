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
COLD_START_SCORE = 0.30

TOP_K = 5

# Ваги для фінального score
W_CENTROID  = 0.40   # Rocchio-центроїд (вже враховує neg всередині)
W_POS_NN    = 0.45   # max similarity з позитивними сусідами
W_NEG_REPEL = 0.15   # штраф за близькість до негативних


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
        text = content.full_text()
        if not text or not text.strip():
            return 0.0

        centroid = await self._profile_repo.get_centroid()
        if centroid is None:
            return COLD_START_SCORE

        article_vec = self._embedder.encode_passage(text)

        # ── 1. Centroid similarity (Rocchio вже зсунутий від негативних) ──────
        centroid_sim = float(np.clip(
            self._embedder.cosine_similarity(article_vec, centroid), 0.0, 1.0
        ))

        # ── 2. Positive NN — max similarity з liked статей ────────────────────
        pos_sims = await self._profile_repo.query_by_feedback_type(
            article_vec, n_results=TOP_K, feedback_type="positive"
        )
        pos_nn = max(pos_sims) if pos_sims else centroid_sim  # fallback

        # ── 3. Negative repulsion — наскільки стаття СХОЖА на disliked ────────
        neg_sims = await self._profile_repo.query_by_feedback_type(
            article_vec, n_results=TOP_K, feedback_type="negative"
        )
        # Якщо немає негативних — штрафу немає
        neg_penalty = max(neg_sims) if neg_sims else 0.0

        # ── 4. Фінальний score ────────────────────────────────────────────────
        # neg_penalty діє як repulsion: чим ближче до disliked — тим менше score
        raw = (
            W_CENTROID  * centroid_sim
            + W_POS_NN  * pos_nn
            - W_NEG_REPEL * neg_penalty
        )

        score = float(np.clip(raw, 0.0, 1.0))

        logger.info(
            "EmbeddingsScoring: centroid=%.3f pos_nn=%.3f neg_penalty=%.3f → %.3f",
            centroid_sim, pos_nn, neg_penalty, score,
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