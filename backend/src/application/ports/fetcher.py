# application/ports/fetcher.py
"""
Порт IFetcher — визначається в application, реалізується в infrastructure.

Повертає ParsedContent, а не RawArticle:
  - Fetcher знає як завантажити і розпарсити контент (infrastructure)
  - Fetcher НЕ знає як створити domain entity (це робота domain service)
  - Це усуває залежність infrastructure → domain entities у зворотний бік

Lifecycle:
  RssFetcher.fetch(source) → list[ParsedContent]
  IngestionDomainService.create_raw_article(source_id, content) → RawArticle
  IRawArticleRepository.save(raw_article)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import ParsedContent


class IFetcher(ABC):
    """
    Абстрактний адаптер для завантаження статей із зовнішніх джерел.

    Реалізації:
      - RssFetcher   — feedparser, для RSS/Atom джерел
      - WebFetcher   — BeautifulSoup / Playwright, для HTML-сторінок
      - ApiFetcher   — для REST/GraphQL джерел
    """

    @abstractmethod
    async def fetch(self, source: Source) -> list[ParsedContent]:
        """
        Завантажити і розпарсити контент із джерела.

        Returns:
            Список ParsedContent — чисті дані без ID, без хешів.
            Порожній список якщо джерело недоступне або пусте.

        Raises:
            SourceUnreachable: якщо HTTP-помилка або timeout
            ParseError:        якщо контент не валідний
        """
        ...