# application/ports/tagger.py
"""
ITagger — порт для тегування статей.

Application layer знає тільки про цей інтерфейс.
Реалізація (EmbeddingTagger) живе в infrastructure/ml/.
Заміна на LLM-based tagger не потребує змін у use cases.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ITagger(ABC):
    """Порт для тегування тексту статті."""

    @abstractmethod
    def tag(self, text: str) -> list[str]:
        """
        Повертає список тегів для тексту.

        Args:
            text: повний текст статті (title + body).

        Returns:
            Список назв тегів, відсортований за релевантністю DESC.
            Порожній список якщо тегів немає.
        """
        ...