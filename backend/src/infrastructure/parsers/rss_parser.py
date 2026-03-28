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

from application.ports import IFetcher, RawArticleDTO, SourceDTO

logger = logging.getLogger(__name__)


class RssFetcher(IFetcher):
    async def fetch(self, source: SourceDTO) -> list[RawArticleDTO]:
        feed = feedparser.parse(source.url)
        articles = []

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            body = getattr(entry, "summary", "") or getattr(entry, "content", [{}])[0].get("value", "")
            url = getattr(entry, "link", "")

            if not title or not url:
                continue

            text = title + body
            content_hash = hashlib.sha256(text.encode()).hexdigest()

            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            articles.append(RawArticleDTO(
                id=uuid4(),
                source_id=source.id,
                title=title,
                body=body,
                url=url,
                language=None,          # мова детектується пізніше
                content_hash=content_hash,
                published_at=published_at,
            ))

        return articles