# infrastructure/scoring/embeddings_scoring_service.py
"""
EmbeddingsScoringService — другий шар scoring у CompositeScoringService.

ПРОБЛЕМА (до фіксу):
  У новинному домені multilingual-e5-small дає cosine sim 0.85–0.95
  між будь-якими двома статтями — вони всі семантично "близькі".
  Через це pos_nn ≈ neg_nn ≈ 0.93, і стара формула:
    raw = W_CENTROID*centroid + W_POS_NN*pos_nn - W_NEG_REPEL*neg_penalty
  завжди давала score ~0.55–0.70 незалежно від реальної релевантності.

РІШЕННЯ — Discriminative Score:
  Замість абсолютних значень sim використовуємо ВІДНОСНУ різницю
  між pos і neg similarity, масштабовану сигмоїдою.

  Кроки:
    1. pos_nn  = max similarity серед TOP_K позитивних сусідів
    2. neg_nn  = max similarity серед TOP_K негативних сусідів
    3. margin  = pos_nn - neg_nn                     ∈ [-1, 1]
       margin > 0 → стаття ближча до liked контенту
       margin < 0 → стаття ближча до disliked контенту
    4. discriminator = sigmoid(margin * SHARPNESS)   ∈ (0, 1)
       SHARPNESS=10 → при margin=+0.05 → disc≈0.73, margin=-0.05 → disc≈0.27
    5. centroid_sim залишається як anchor (стабільніший сигнал)
    6. Фінал: W_CENTROID*centroid + W_DISC*discriminator

  Якщо профіль порожній (cold start) → COLD_START_SCORE = 0.30

Приклад з вашими даними:
  pos_nn=0.931, neg_nn=0.916 → margin=+0.015 → disc≈0.54  (нейтрально)
  pos_nn=0.950, neg_nn=0.880 → margin=+0.070 → disc≈0.84  (явно позитивна)
  pos_nn=0.870, neg_nn=0.940 → margin=-0.070 → disc≈0.16  (явно негативна)

Налаштування:
  SHARPNESS = 10   — крутість сигмоїди (більше → чіткіший поріг)
  W_CENTROID = 0.35
  W_DISC     = 0.65
  TOP_K = 5
"""
from __future__ import annotations

import logging
import math

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.ml.embedder import Embedder
from src.infrastructure.vector_store.interest_profile_repo import InterestProfileRepository

logger = logging.getLogger(__name__)

COLD_START_SCORE = 0.30
TOP_K = 5

# Ваги фінального score
W_CENTROID = 0.35   # Rocchio-центроїд (стабільний довгостроковий сигнал)
W_DISC     = 0.65   # Discriminator (pos vs neg, короткостроковий сигнал)

# Крутість сигмоїди для margin
# При SHARPNESS=10: margin=±0.05 → score≈0.73/0.27; margin=±0.10 → score≈0.88/0.12
SHARPNESS = 10.0


def _sigmoid(x: float) -> float:
    """Стандартна сигмоїда, стабільна для великих |x|."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        exp_x = math.exp(x)
        return exp_x / (1.0 + exp_x)


class EmbeddingsScoringService(IScoringService):
    """
    Discriminative scoring через порівняння з pos/neg профілем.

    Ключова відмінність від попередньої версії:
      Стара: score = f(abs_pos_sim, abs_neg_sim)   → ігнорує відносну різницю
      Нова:  score = f(centroid, sigmoid(pos-neg)) → фокусується на різниці

    Це вирішує проблему "все має score ~0.6" коли pos_nn ≈ neg_nn.
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

        # ── Cold start: профіль порожній ─────────────────────────────────────
        centroid = await self._profile_repo.get_centroid()
        if centroid is None:
            return COLD_START_SCORE

        article_vec = self._embedder.encode_passage(text)

        # ── 1. Centroid similarity (Rocchio-зсунутий від негативних) ─────────
        centroid_sim = float(np.clip(
            self._embedder.cosine_similarity(article_vec, centroid), 0.0, 1.0
        ))

        # ── 2. Positive NN ────────────────────────────────────────────────────
        pos_sims = await self._profile_repo.query_by_feedback_type(
            article_vec, n_results=TOP_K, feedback_type="positive"
        )
        pos_nn = max(pos_sims) if pos_sims else centroid_sim  # fallback на centroid

        # ── 3. Negative NN ────────────────────────────────────────────────────
        neg_sims = await self._profile_repo.query_by_feedback_type(
            article_vec, n_results=TOP_K, feedback_type="negative"
        )
        neg_nn = max(neg_sims) if neg_sims else None

        # ── 4. Discriminator ──────────────────────────────────────────────────
        if neg_nn is None:
            # Немає негативних → discriminator = pos_nn (стара логіка)
            discriminator = pos_nn
        else:
            # Відносна різниця, масштабована сигмоїдою
            # margin > 0 → ближче до liked; margin < 0 → ближче до disliked
            margin = pos_nn - neg_nn
            discriminator = _sigmoid(margin * SHARPNESS)

        # ── 5. Фінальний score ────────────────────────────────────────────────
        raw = W_CENTROID * centroid_sim + W_DISC * discriminator
        score = float(np.clip(raw, 0.0, 1.0))

        logger.info(
            "EmbeddingsScoring: centroid=%.3f pos_nn=%.3f neg_nn=%s margin=%s disc=%.3f → %.3f",
            centroid_sim,
            pos_nn,
            f"{neg_nn:.3f}" if neg_nn is not None else "None",
            f"{(pos_nn - neg_nn):.4f}" if neg_nn is not None else "N/A",
            discriminator,
            score,
        )
        return score

    async def encode(self, content: ParsedContent) -> np.ndarray:
        """
        Повертає вектор статті (384-dim, float32).
        Використовується у ProfileLearner і для пошуку схожих статей.
        """
        text = content.full_text()
        return self._embedder.encode_passage(text)