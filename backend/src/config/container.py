# config/container.py
"""
DI Container — збирає граф залежностей.

Lifecycle:
  1. init_container() → ONE TIME in lifespan
  2. get_container()  → роутери та workers

Container НЕ є god-object для бізнес-логіки.
Він лише збирає залежності і надає фабричні методи.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.ports.task_queue import ITaskQueue
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class Container:
    """
    Singleton-контейнер залежностей.

    Singleton: engine, session_factory, task_queue
    Per-request: session, репозиторії, use cases
    """

    def __init__(self) -> None:
        settings = get_settings()

        self._engine = create_async_engine(
            settings.database.url,
            echo=settings.app_debug,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

        from src.infrastructure.task_queue.factory import build_task_queue
        self.task_queue: ITaskQueue = build_task_queue(settings.task_queue)

        self._chroma_client = None
        logger.info("Container initialized")

    # ── DB Session ────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def db_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            async with session.begin():
                yield session

    # ── Chroma ────────────────────────────────────────────────────────────────

    async def _get_chroma(self):
        if self._chroma_client is None:
            from src.infrastructure.vector_store.chroma_client import build_chroma_client
            self._chroma_client = build_chroma_client()
        return self._chroma_client

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._engine.dispose()
        logger.info("Container closed")

    # ══════════════════════════════════════════════════════════════════════════
    # ФАБРИЧНІ МЕТОДИ — USE CASES
    # ══════════════════════════════════════════════════════════════════════════

    # ── Ingestion pipeline ────────────────────────────────────────────────────

    def ingest_source_uc(self, session: AsyncSession):
        """
        IngestSourceUseCase — завантажити сирі статті для одного джерела.
        IFetcher повертає ParsedContent; domain service створює RawArticle.
        """
        from src.application.use_cases.ingest_source import IngestSourceUseCase
        from src.infrastructure.parsers.rss_parser import RssFetcher
        from src.infrastructure.persistence.repositories.fetch_job_repo import SqlAlchemyFetchJobRepository
        from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return IngestSourceUseCase(
            source_repo=SqlAlchemySourceRepository(session),
            raw_article_repo=SqlAlchemyRawArticleRepository(session),
            fetch_job_repo=SqlAlchemyFetchJobRepository(session),
            fetcher=RssFetcher(),
        )

    def process_articles_uc_standalone(self):
        """
        ProcessArticlesUseCase — окрема транзакція на статтю.
        Отримує реальні ILanguageDetector і IScoringService через порти.
        """
        from src.application.use_cases.process_articles import ProcessArticlesUseCase
        from src.infrastructure.adapters.lang_detect_adapter import LangDetectAdapter
        from src.infrastructure.scoring.keyword_scoring_service import KeywordScoringService
        from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository

        cfg = get_settings()
        return ProcessArticlesUseCase(
            session_factory=self._session_factory,
            raw_repo_factory=lambda session: SqlAlchemyRawArticleRepository(session),
            article_repo_factory=lambda session: SqlAlchemyArticleRepository(session),
            language_detector=LangDetectAdapter(),
            scoring_service=KeywordScoringService(),
            threshold=cfg.filtering.default_threshold,
        )

    def startup_uc(self, session: AsyncSession):
        from src.application.use_cases.startup import StartupUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return StartupUseCase(
            source_repo=SqlAlchemySourceRepository(session),
            task_queue=self.task_queue,
        )

    # ── Sources ───────────────────────────────────────────────────────────────

    def add_source_uc(self, session: AsyncSession):
        from src.application.use_cases.add_source import AddSourceUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return AddSourceUseCase(source_repo=SqlAlchemySourceRepository(session))

    def list_sources_uc(self, session: AsyncSession):
        from src.application.use_cases.list_sources import ListSourcesUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return ListSourcesUseCase(source_repo=SqlAlchemySourceRepository(session))

    def deactivate_source_uc(self, session: AsyncSession):
        from src.application.use_cases.deactivate_source import DeactivateSourceUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return DeactivateSourceUseCase(source_repo=SqlAlchemySourceRepository(session))

    # ── Articles ──────────────────────────────────────────────────────────────

    def list_articles_uc(self, session: AsyncSession):
        from src.application.use_cases.list_articles import ListArticlesUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return ListArticlesUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def get_article_uc(self, session: AsyncSession):
        from src.application.use_cases.get_article import GetArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return GetArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def submit_feedback_uc(self, session: AsyncSession):
        from src.application.use_cases.submit_feedback import SubmitFeedbackUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.infrastructure.persistence.repositories.feed_repo import (
            SqlAlchemyFeedbackRepository, SqlAlchemyFeedRepository,
        )
        return SubmitFeedbackUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            feedback_repo=SqlAlchemyFeedbackRepository(session),
            feed_repo=SqlAlchemyFeedRepository(session),
        )

    def create_article_uc(self, session: AsyncSession):
        from src.application.use_cases.create_article import CreateArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return CreateArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def update_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import UpdateArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return UpdateArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def delete_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import DeleteArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return DeleteArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def tag_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import TagArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return TagArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    def expire_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import ExpireArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return ExpireArticleUseCase(article_repo=SqlAlchemyArticleRepository(session))

    # ── Feed ──────────────────────────────────────────────────────────────────

    def build_feed_uc(self, session: AsyncSession):
        from src.application.use_cases.build_feed import BuildFeedUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.infrastructure.persistence.repositories.feed_repo import SqlAlchemyFeedRepository
        return BuildFeedUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            feed_repo=SqlAlchemyFeedRepository(session),
        )

    def mark_article_read_uc(self, session: AsyncSession):
        from src.application.use_cases.mark_article_read import MarkArticleReadUseCase
        from src.infrastructure.persistence.repositories.feed_repo import SqlAlchemyFeedRepository
        return MarkArticleReadUseCase(feed_repo=SqlAlchemyFeedRepository(session))

    # ── Health ────────────────────────────────────────────────────────────────

    def article_repo(self, session: AsyncSession):
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return SqlAlchemyArticleRepository(session)

    # ── Vector Store ──────────────────────────────────────────────────────────

    async def article_vector_repo(self):
        from src.infrastructure.vector_store.article_vector_repo import ArticleVectorRepository
        client = await self._get_chroma()
        return ArticleVectorRepository(client)

    async def criteria_vector_repo(self):
        from src.infrastructure.vector_store.criteria_vector_repo import CriteriaVectorRepository
        client = await self._get_chroma()
        return CriteriaVectorRepository(client)

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _get_minhash_repo(self):
        settings = get_settings()
        if settings.is_dev:
            from src.infrastructure.dedup.minhash_repo import InMemoryMinHashRepository
            if not hasattr(self, "_minhash_repo_instance"):
                self._minhash_repo_instance = InMemoryMinHashRepository()
            return self._minhash_repo_instance
        else:
            from src.infrastructure.dedup.minhash_repo import RedisMinHashRepository
            return RedisMinHashRepository(self._redis)

    def deduplicate_uc(self, session: AsyncSession):
        from src.application.use_cases.deduplicate_article import DeduplicateRawArticleUseCase
        from src.domain.deduplication.services import DeduplicationDomainService
        from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository

        cfg = get_settings()
        return DeduplicateRawArticleUseCase(
            raw_repo=SqlAlchemyRawArticleRepository(session),
            article_repo=SqlAlchemyArticleRepository(session),
            minhash_repo=self._get_minhash_repo(),
            dedup_service=DeduplicationDomainService(num_perm=cfg.dedup.minhash_num_perm),
            minhash_threshold=cfg.dedup.minhash_threshold,
        )

    def batch_deduplicate_uc(self, session: AsyncSession):
        from src.application.use_cases.deduplicate_article import BatchDeduplicateUseCase
        return BatchDeduplicateUseCase(single_uc=self.deduplicate_uc(session))


# ── Singleton ─────────────────────────────────────────────────────────────────

_container: Container | None = None


def init_container() -> Container:
    global _container
    _container = Container()
    return _container


def get_container() -> Container:
    if _container is None:
        raise RuntimeError("Container not initialized. Call init_container() in lifespan first.")
    return _container