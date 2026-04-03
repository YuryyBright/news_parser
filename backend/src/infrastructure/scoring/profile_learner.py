# infrastructure/scoring/profile_learner.py
"""
ProfileLearner — реалізує IProfileLearner.

Місток між ProcessArticlesUseCase і ChromaDB:
  - Отримує текст статті
  - Кодує через Embedder
  - Зберігає вектор у InterestProfileRepository

Чому окремий клас а не напряму InterestProfileRepository:
  - UseCase не повинен знати про embedder (це infrastructure)
  - Testability: можна мокати IProfileLearner без реального ChromaDB
  - Єдина відповідальність: "закодуй і збережи"
"""
from __future__ import annotations

import logging
from uuid import UUID

from src.application.use_cases.process_articles import IProfileLearner
from src.infrastructure.ml.embedder import Embedder
from src.infrastructure.vector_store.interest_profile_repo import InterestProfileRepository

logger = logging.getLogger(__name__)


class ProfileLearner(IProfileLearner):
    """
    Реалізує implicit feedback: текст → вектор → профіль.

    Args:
        embedder:     Embedder.instance() — singleton моделі
        profile_repo: InterestProfileRepository — ChromaDB колекція
    """

    def __init__(
        self,
        embedder: Embedder,
        profile_repo: InterestProfileRepository,
    ) -> None:
        self._embedder = embedder
        self._profile_repo = profile_repo

    async def add_to_profile(
        self,
        article_id: UUID,
        content_text: str,
        score: float,
        tags: list[str],
    ) -> None:
        """
        Кодує текст і зберігає вектор у профіль інтересів.
        Ідемпотентно — якщо article вже є, оновлює (upsert).
        """
        if not content_text or not content_text.strip():
            logger.debug("ProfileLearner: empty text for article=%s, skipping", article_id)
            return

        # Кодуємо як passage (документ, не запит)
        vector = self._embedder.encode_passage(content_text)

        await self._profile_repo.add(
            article_id=article_id,
            vector=vector,
            score=score,
            tags=tags,
        )

        logger.debug(
            "ProfileLearner: saved article=%s score=%.3f tags=%s",
            article_id, score, tags,
        )

    async def remove_from_profile(self, article_id: UUID) -> bool:
        """
        Видаляє вектор статті з профілю (explicit dislike).

        Викликається з SubmitFeedbackUseCase при liked=False.
        Idempotent — якщо статті нема у профілі, просто повертає False.

        Returns:
            True  — вектор видалено.
            False — вектора не було у профілі.
        """
        removed = await self._profile_repo.remove(article_id)
        if removed:
            logger.info("ProfileLearner: removed article=%s from profile (dislike)", article_id)
        return removed