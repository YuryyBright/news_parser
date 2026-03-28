# domain/filtering/services.py
from dataclasses import dataclass
import numpy as np
from .value_objects import RelevanceScore, EmbeddingVector
from .entities import FilterCriteria, FilterResult

@dataclass
class SignalWeights:
    embedding: float = 0.60   # семантична схожість
    keyword: float = 0.25     # точний збіг ключових слів
    feedback: float = 0.15    # персональний feedback
    
    def __post_init__(self):
        assert abs(self.embedding + self.keyword + self.feedback - 1.0) < 1e-6


class FilteringDomainService:
    """
    Чиста доменна логіка — без залежностей від ML фреймворків.
    ML моделі інжектуються через інтерфейси із infrastructure.
    """

    def compute_relevance(
        self,
        article_embedding: EmbeddingVector,
        article_text: str,
        criteria: FilterCriteria,
        weights: SignalWeights | None = None,
    ) -> FilterResult:
        w = weights or SignalWeights()

        # --- Signal 1: Embedding cosine similarity (multilingual) ---
        # max по всіх criteria-фразах — одна влучна фраза = стаття релевантна
        emb_score = self._max_cosine_sim(article_embedding.vector, criteria.phrase_embeddings)

        # --- Signal 2: Keyword exact/fuzzy match ---
        kw_score = self._keyword_score(article_text, criteria.keywords)

        # --- Signal 3: Feedback prior (баєсівський апдейт) ---
        # Початкове значення 0.5 (нейтральне), зростає з лайками
        fb_score = criteria.feedback_prior  # float [0, 1]

        # --- Weighted combination ---
        final = (
            w.embedding * emb_score
            + w.keyword  * kw_score
            + w.feedback * fb_score
        )

        return FilterResult(
            score=round(final, 4),
            passed=final >= criteria.threshold,
            emb_score=emb_score,
            kw_score=kw_score,
            fb_score=fb_score,
            method="hybrid",
        )

    def _max_cosine_sim(self, article_vec: np.ndarray, criteria_vecs: np.ndarray) -> float:
        if criteria_vecs is None or len(criteria_vecs) == 0:
            return 0.0
        # обидва вже нормалізовані → cosine = dot product
        sims = criteria_vecs @ article_vec
        return float(sims.max())

    def _keyword_score(self, text: str, keywords: list[str]) -> float:
        if not keywords:
            return 0.0
        text_lower = text.lower()
        hits = sum(1 for kw in keywords if kw.lower() in text_lower)
        # м'який скор: логарифмічне насичення щоб 1 збіг != 10 збігів
        import math
        return min(1.0, math.log1p(hits) / math.log1p(max(3, len(keywords) * 0.5)))