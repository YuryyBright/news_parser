"""
Порт ITranslator — визначається в application, реалізується в infrastructure.
Use case залежить тільки від цього інтерфейсу.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    text: str
    detected_language: str | None  # якщо backend сам визначив мову


class ITranslator(ABC):
    @abstractmethod
    async def translate(
        self,
        text: str,
        target_language: str = "en",
        source_language: str | None = None,  # None → auto-detect
    ) -> TranslationResult:
        """
        Перекласти текст.
        Returns:
            TranslationResult з перекладеним текстом та виявленою мовою.
        Raises:
            TranslationError при збої backend'у.
        """
        ...

    @abstractmethod
    def should_translate(self, language: str, target_language: str = "en") -> bool:
        """
        Чи варто перекладати текст з цієї мови.
        Дозволяє skip для вже цільової мови або 'unknown'.
        """
        ...


class TranslationError(Exception):
    """Збій translation backend'у."""