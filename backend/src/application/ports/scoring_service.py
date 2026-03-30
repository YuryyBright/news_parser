# application/ports/scoring_service.py
"""
Порт IScoringService — визначається в application, реалізується в infrastructure.

Scoring — це NLP/ML операція, яка не може жити в домені
(залежить від зовнішніх моделей, векторних БД, конфігурації).
Use case отримує score і вирішує accept/reject — це його відповідальність.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ingestion.value_objects import ParsedContent


class IScoringService(ABC):

    @abstractmethod
    async def score(self, content: ParsedContent) -> float:
        """
        Обчислити relevance score для контенту.

        Returns:
            float ∈ [0.0, 1.0] — де 1.0 = максимально релевантно
        """
        ...