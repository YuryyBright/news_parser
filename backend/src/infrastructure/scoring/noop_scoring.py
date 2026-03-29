# infrastructure/scoring/noop_scoring.py
"""
NoOpScoringService — заглушка для тестів і dev-режиму.

Повертає 0.0 (всі статті будуть rejected при порозі > 0).
Замінити на EmbeddingsScoringService коли ChromaDB готова.
"""
from __future__ import annotations

from uuid import UUID

from src.application.use_cases.filter_article import IScoringService


class NoOpScoringService(IScoringService):
    async def score(self, article_id: UUID, user_profile_id: UUID | None = None) -> float:
        return 0.0


class FixedScoringService(IScoringService):
    """Для тестів — завжди повертає заданий score."""
    def __init__(self, fixed_score: float = 0.75) -> None:
        self._score = fixed_score

    async def score(self, article_id: UUID, user_profile_id: UUID | None = None) -> float:
        return self._score
