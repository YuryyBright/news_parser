# application/use_cases/ingest_source.py
"""
IngestSourceUseCase — завантажує і зберігає сирі статті для одного джерела.

Pipeline:
  1. Отримати Source з репозиторію
  2. Запустити FetchJob (start)
  3. IFetcher.fetch(source) → list[ParsedContent]
  4. Для кожного ParsedContent:
     a. dedup check (url + hash) проти raw_articles
     b. IngestionDomainService.create_raw_article() → RawArticle
     c. IRawArticleRepository.save(raw_article)
  5. FetchJob.complete() або fail()

Dependency rule:
  ✅ domain interfaces (ISourceRepository, IRawArticleRepository, IFetchJobRepository)
  ✅ application ports (IFetcher)
  ✅ domain service (IngestionDomainService)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
from src.domain.ingestion.repositories import IFetchJobRepository, IRawArticleRepository, ISourceRepository
from src.domain.ingestion.services import IngestionDomainService
from src.domain.ingestion.exceptions import SourceUnreachable, ParseError

logger = logging.getLogger(__name__)


@dataclass
class IngestSourceResult:
    source_id: UUID
    fetched: int = 0
    saved: int = 0
    skipped_duplicates: int = 0
    error: str | None = None


class IngestSourceUseCase:

    def __init__(
        self,
        source_repo: ISourceRepository,
        raw_article_repo: IRawArticleRepository,
        fetch_job_repo: IFetchJobRepository,
        fetcher: IFetcher,
    ) -> None:
        self._sources    = source_repo
        self._raw        = raw_article_repo
        self._jobs       = fetch_job_repo
        self._fetcher    = fetcher
        self._domain_svc = IngestionDomainService()

    async def execute(self, source_id: UUID) -> IngestSourceResult:
        result = IngestSourceResult(source_id=source_id)

        # ── 1. Отримати джерело ───────────────────────────────────────────────
        source = await self._sources.get(source_id)
        if not source or not source.is_active:
            result.error = f"Source {source_id} not found or inactive"
            return result

        # ── 2. FetchJob ───────────────────────────────────────────────────────
        job = await self._jobs.get_by_source_id(source_id)
        if job is None:
            from src.domain.ingestion.entities import FetchJob
            job = FetchJob(source_id=source_id)
            await self._jobs.save(job)

        job.start()
        await self._jobs.update(job)

        # ── 3. Fetch ──────────────────────────────────────────────────────────
        try:
            parsed_contents = await self._fetcher.fetch(source)
        except (SourceUnreachable, ParseError) as exc:
            job.fail(str(exc))
            await self._jobs.update(job)
            result.error = str(exc)
            logger.warning("Fetch failed for source %s: %s", source_id, exc)
            return result
        except Exception as exc:
            job.fail(str(exc))
            await self._jobs.update(job)
            result.error = f"Unexpected error: {exc}"
            logger.exception("Unexpected fetch error for source %s", source_id)
            return result

        result.fetched = len(parsed_contents)
        logger.info("Fetched %d items from source %s", result.fetched, source_id)

        # ── 4. Dedup + Save ───────────────────────────────────────────────────
        for content in parsed_contents:
            # Dedup рівень 1: URL
            if await self._raw.exists_by_url(content.url):
                result.skipped_duplicates += 1
                continue

            # Dedup рівень 2: content hash (обчислюється в ParsedContent)
            if await self._raw.exists_by_hash(content.content_hash):
                result.skipped_duplicates += 1
                continue

            # Доменний сервіс створює RawArticle і генерує подію ArticleIngested
            raw_article = self._domain_svc.create_raw_article(
                source_id=source.id,
                content=content,
            )
            await self._raw.save(raw_article)
            result.saved += 1

        # ── 5. Complete ───────────────────────────────────────────────────────
        job.complete()
        await self._jobs.update(job)

        logger.info(
            "IngestSource done: source=%s fetched=%d saved=%d skipped=%d",
            source_id, result.fetched, result.saved, result.skipped_duplicates,
        )
        return result