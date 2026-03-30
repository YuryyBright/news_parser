# infrastructure/parsers/rss_parser.py
"""
RssFetcher — реалізує IFetcher для RSS/Atom джерел.

Повертає list[ParsedContent] — чисті дані без ID і без хешів.
Створення RawArticle і обчислення хешу — відповідальність
IngestionDomainService, а не fetcher'а.

Application layer (IngestSourceUseCase) знає тільки про IFetcher.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)


class RssFetcher(IFetcher):

    async def fetch(self, source: Source) -> list[ParsedContent]:
        feed = feedparser.parse(source.url)

        results: list[ParsedContent] = []
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            url   = getattr(entry, "link", "").strip()

            if not title or not url:
                logger.debug("Skipping entry without title or url: %s", entry)
                continue

            body = (
                getattr(entry, "summary", "")
                or (getattr(entry, "content", [{}])[0].get("value", ""))
            ).strip()

            published_at: datetime | None = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            try:
                content = ParsedContent(
                    title=title,
                    body=body,
                    url=url,
                    published_at=published_at,
                    language=None,      # detect later in ProcessArticlesUseCase
                )
                results.append(content)
            except Exception as exc:
                logger.warning("Skipping invalid entry url=%s: %s", url, exc)

        return results