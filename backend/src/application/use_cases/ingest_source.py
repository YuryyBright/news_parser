# application/use_cases/ingest_source.py
"""
IngestSourceUseCase — серце ingestion pipeline.

Відповідальність:
  1. Завантажити сирі статті через IFetcher (RssFetcher / WebFetcher)
  2. Дедуплікувати: пропустити вже відомі за URL і content hash
  3. Зберегти нові RawArticle в IRawArticleRepository
  4. Зафіксувати результат FetchJob (done / failed)

Use case НЕ:
  - НЕ парсить HTML/RSS напряму (це IFetcher)
  - НЕ детектує мову чи рахує score (це ProcessArticlesUseCase)
  - НЕ знає про HTTP або Celery
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import FetchJob, FetchJobStatus
from src.domain.ingestion.exceptions import ParseError, SourceUnreachable
from src.domain.ingestion.repositories import (
    IFetchJobRepository,
    IRawArticleRepository,
    ISourceRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestSourceResult:
    """Результат одного запуску ingestion для джерела."""
    source_id: UUID
    fetched: int = 0
    saved: int = 0
    skipped_duplicates: int = 0
    error: str | None = None


class IngestSourceUseCase:
    """
    Завантажує та зберігає сирі статті для одного джерела.

    Викликається з handle_ingest_source (worker handler).
    Не знає нічого про HTTP, feedparser, Celery.
    """

    def __init__(
        self,
        source_repo: ISourceRepository,
        raw_article_repo: IRawArticleRepository,
        fetch_job_repo: IFetchJobRepository,
        fetcher: IFetcher,
    ) -> None:
        self._source_repo      = source_repo
        self._raw_article_repo = raw_article_repo
        self._fetch_job_repo   = fetch_job_repo
        self._fetcher          = fetcher

    async def execute(self, source_id: UUID) -> IngestSourceResult:
        result = IngestSourceResult(source_id=source_id)

        # ── 1. Завантажити джерело ─────────────────────────────────────────
        source = await self._source_repo.get(source_id)
        if source is None:
            result.error = f"Source {source_id} not found"
            logger.error(result.error)
            return result

        if not source.is_active:
            result.error = f"Source {source_id} is inactive, skipping"
            logger.warning(result.error)
            return result

        # ── 2. Знайти або створити FetchJob ────────────────────────────────
        job = await self._get_or_create_job(source_id)
        job.start()
        await self._fetch_job_repo.save(job)

        # ── 3. Fetching + обробка помилок ──────────────────────────────────
        try:
            raw_articles = await self._fetcher.fetch(source)
        except (SourceUnreachable, ParseError) as exc:
            result.error = str(exc)
            job.fail(reason=str(exc), max_retries=3)
            await self._fetch_job_repo.save(job)
            logger.warning(
                "ingest_source failed for %s: %s (retries=%d)",
                source_id, exc, job.retries,
            )
            return result

        result.fetched = len(raw_articles)

        # ── 4. Дедуплікація і збереження ──────────────────────────────────
        for article in raw_articles:
            url          = article.content.url
            content_hash = _compute_hash(article.content.title, article.content.body)

            # Рівень 1: дедуп за URL (найшвидший — є унікальний індекс)
            if await self._raw_article_repo.exists_by_url(url):
                result.skipped_duplicates += 1
                continue

            # Рівень 2: дедуп за SHA-256 (ловить перевидані статті)
            if await self._raw_article_repo.exists_by_hash(content_hash):
                result.skipped_duplicates += 1
                continue

            await self._raw_article_repo.save(article)
            result.saved += 1

        # ── 5. Завершити job ───────────────────────────────────────────────
        job.complete()
        await self._fetch_job_repo.save(job)

        logger.info(
            "ingest_source done: source=%s fetched=%d saved=%d skipped=%d",
            source_id, result.fetched, result.saved, result.skipped_duplicates,
        )
        return result

    async def _get_or_create_job(self, source_id: UUID) -> FetchJob:
        """
        Знайти існуючий FetchJob для джерела або створити новий.
        Зазвичай job один на джерело — переходить між статусами.
        """
        pending_jobs = await self._fetch_job_repo.get_pending(limit=1)
        for job in pending_jobs:
            if job.source_id == source_id:
                return job

        # Нового job — якщо не знайшли
        new_job = FetchJob(
            id=__import__("uuid").uuid4(),
            source_id=source_id,
        )
        await self._fetch_job_repo.save(new_job)
        return new_job


def _compute_hash(title: str, body: str) -> str:
    """SHA-256 від title+body — для дедуплікації за контентом."""
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()