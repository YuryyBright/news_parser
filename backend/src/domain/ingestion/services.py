# domain/ingestion/services.py
"""
IngestionDomainService — чиста доменна логіка.

Що тут є:
  - фабрика RawArticle (хеш обчислюється тут, а не в fetcher'і)
  - логіка re-fetch

Чого тут НЕМАЄ:
  - HTTP, feedparser, SQL
  - asyncio (сервіс синхронний — тільки обчислення)
"""
from __future__ import annotations

from datetime import datetime, timezone

from .entities import FetchJob, RawArticle
from .value_objects import ParsedContent
from .exceptions import SourceUnreachable


class IngestionDomainService:

    def create_raw_article(
        self,
        source_id,          # UUID — джерело
        content: ParsedContent,
    ) -> RawArticle:
        """
        Єдина точка створення RawArticle.

        content_hash делегується в ParsedContent.content_hash,
        тому fetcher'и і use cases не рахують хеш самостійно.
        ID призначається тут через __post_init__ у RawArticle.
        """
        article = RawArticle(
            source_id=source_id,
            content=content,
        )
        article.mark_ingested()
        return article

    def should_refetch(self, job: FetchJob, schedule_seconds: int) -> bool:
        if job.last_run_at is None:
            return True
        elapsed = (datetime.now(timezone.utc) - job.last_run_at).total_seconds()
        return elapsed >= schedule_seconds