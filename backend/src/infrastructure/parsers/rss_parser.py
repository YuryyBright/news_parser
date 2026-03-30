# infrastructure/parsers/rss_parser.py
"""
Адаптер для RSS-джерел.
Реалізує IFetcher — application не знає що тут feedparser.
"""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

import feedparser


from src.domain.ingestion.entities import Source, RawArticle
from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.value_objects import ParsedContent
logger = logging.getLogger(__name__)


class RssFetcher(IFetcher):  # ← було FetchJob
    async def fetch(self, source: Source) -> list[RawArticle]:
        feed = feedparser.parse(source.url)
        articles = []
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            body = getattr(entry, "summary", "") or getattr(entry, "content", [{}])[0].get("value", "")
            url = getattr(entry, "link", "")
            if not title or not url:
                continue

            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            content = ParsedContent(          # ← ключове — треба створити
                title=title,
                body=body,
                url=url,
                published_at=published_at,
                language=None,
            )
            content_hash = hashlib.sha256(content.full_text().encode()).hexdigest()

            articles.append(RawArticle(
                id=uuid4(),
                source_id=source.id,
                content=content,              # ← заповнюємо content
                content_hash=content_hash,
            ))
        return articles