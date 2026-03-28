# application/use_cases/ingest_source.py
"""
Use case: отримати статті з одного джерела.

Залежності приходять ТІЛЬКИ через інтерфейси з ports.py.
Жодних імпортів з infrastructure або FastAPI!
"""
from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

from application.ports import (
    ISourceRepository,
    IRawArticleRepository,
    IFetchJobRepository,
    IFetcher,
    RawArticleDTO,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestSourceResult:
    source_id: UUID
    job_id: UUID
    fetched: int
    saved: int
    skipped_duplicates: int
    error: str | None = None


class IngestSourceUseCase:
    """
    Отримує статті з конкретного джерела:
    1. Створює FetchJob
    2. Викликає IFetcher (адаптер — RSS або scraper)
    3. Перевіряє дублікати через content_hash
    4. Зберігає нові RawArticle
    5. Оновлює статус FetchJob
    """

    def __init__(
        self,
        source_repo: ISourceRepository,
        raw_article_repo: IRawArticleRepository,
        fetch_job_repo: IFetchJobRepository,
        fetcher: IFetcher,           # конкретний адаптер передає infrastructure/container
    ) -> None:
        self._sources = source_repo
        self._raw_articles = raw_article_repo
        self._jobs = fetch_job_repo
        self._fetcher = fetcher

    async def execute(self, source_id: UUID) -> IngestSourceResult:
        source = await self._sources.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source {source_id} not found")

        job_id = await self._jobs.create(source_id)
        await self._jobs.mark_running(job_id)

        try:
            raw_articles = await self._fetcher.fetch(source)
            logger.info("Fetched %d articles from %s", len(raw_articles), source.name)
        except Exception as exc:
            await self._jobs.mark_failed(job_id, str(exc))
            return IngestSourceResult(
                source_id=source_id, job_id=job_id,
                fetched=0, saved=0, skipped_duplicates=0, error=str(exc),
            )

        saved = 0
        skipped = 0
        for article in raw_articles:
            # Забезпечуємо content_hash якщо fetcher не встановив
            article = _ensure_hash(article)

            if await self._raw_articles.exists_by_hash(article.content_hash):
                skipped += 1
                continue

            await self._raw_articles.save(article)
            saved += 1

        await self._jobs.mark_done(job_id)
        logger.info("Saved %d, skipped %d duplicates from %s", saved, skipped, source.name)

        return IngestSourceResult(
            source_id=source_id, job_id=job_id,
            fetched=len(raw_articles), saved=saved, skipped_duplicates=skipped,
        )


def _ensure_hash(article: RawArticleDTO) -> RawArticleDTO:
    if article.content_hash:
        return article
    digest = hashlib.sha256((article.title + article.body).encode()).hexdigest()
    return RawArticleDTO(**{**article.__dict__, "content_hash": digest})