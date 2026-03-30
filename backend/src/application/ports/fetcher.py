# application/ports/fetcher.py
"""
Порт для fetcher-адаптерів.

Application визначає ЩО потрібно (інтерфейс IFetcher).
Infrastructure реалізує ЯК (RssFetcher, WebFetcher тощо).

Use cases та handlers знають тільки про IFetcher — не про feedparser.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ingestion.entities import RawArticle, Source


class IFetcher(ABC):
    """
    Абстрактний адаптер для завантаження статей із зовнішніх джерел.

    Реалізації:
      - RssFetcher   — feedparser, для RSS/Atom джерел
      - WebFetcher   — BeautifulSoup / Playwright, для HTML-сторінок
      - ApiFetcher   — для REST/GraphQL джерел
    """

    @abstractmethod
    async def fetch(self, source: Source) -> list[RawArticle]:
        """
        Завантажити статті із джерела.

        Args:
            source: доменна сутність джерела з конфігурацією (url, headers тощо)

        Returns:
            Список RawArticle — ще не збережених, без ID у БД.
            Порожній список якщо джерело недоступне або пусте.

        Raises:
            SourceUnreachable: якщо HTTP-помилка або timeout
            ParseError:        якщо контент не валідний
        """
        ...