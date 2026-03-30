# application/ports/language_detector.py
"""
Порт ILanguageDetector — визначається в application, реалізується в infrastructure.

Use case залежить тільки від цього інтерфейсу.
Конкретна бібліотека (langdetect, fasttext, lingua) — деталь infrastructure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ILanguageDetector(ABC):

    @abstractmethod
    async def detect(self, text: str) -> str:
        """
        Визначити мову тексту.

        Returns:
            ISO 639-1 код ('uk', 'en', 'de', ...) або 'unknown'
        """
        ...