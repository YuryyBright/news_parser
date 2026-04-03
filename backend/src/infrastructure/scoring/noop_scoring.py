# infrastructure/scoring/noop_scoring.py
"""
NoOpScoringService та FixedScoringService — заглушки для тестів і dev-режиму.

Використання:
  NoOpScoringService  → повертає 0.0 (всі статті reject при threshold > 0)
  FixedScoringService → повертає заданий score (для детермінованих тестів)

Де підключається:
  container.py → filter_article_uc() → fallback якщо scoring pipeline
  не ініціалізований (healthcheck / тести без init_async).

ВАЖЛИВО: підпис score(content: ParsedContent) відповідає IScoringService.
  Старий підпис score(article_id, user_profile_id) — видалено, він не сумісний
  з поточним портом IScoringService і ніколи не використовувався у production.
"""
from __future__ import annotations

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent


class NoOpScoringService(IScoringService):
    """Повертає 0.0 — всі статті будуть відхилені при threshold > 0."""

    async def score(self, content: ParsedContent) -> float:
        return 0.0


class FixedScoringService(IScoringService):
    """
    Для тестів — завжди повертає заданий score незалежно від контенту.

    Приклад:
        scoring = FixedScoringService(fixed_score=0.75)
        score = await scoring.score(content)  # → 0.75
    """

    def __init__(self, fixed_score: float = 0.75) -> None:
        if not 0.0 <= fixed_score <= 1.0:
            raise ValueError(f"fixed_score must be in [0.0, 1.0], got {fixed_score}")
        self._score = fixed_score

    async def score(self, content: ParsedContent) -> float:
        return self._score