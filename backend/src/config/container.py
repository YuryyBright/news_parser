# config/container.py
"""
DI Container — збирає граф залежностей.

Lifecycle:
  1. init_container() → ONE TIME in lifespan
  2. get_container()  → роутери та workers

Правила імпортів:
  ✅ from config.settings import get_settings
  ❌ від src.config.* — зайвий префікс
  ❌ ніяких імпортів на рівні модуля з infrastructure —
     тільки всередині методів або __init__, щоб уникнути
     circular imports при тестуванні.

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

    Singleton: engine, session_factory, task_queue, chroma_client
    Per-request: session, репозиторії, use cases
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── SQLAlchemy ────────────────────────────────────────────────────────
        self._engine = create_async_engine(
            settings.database.url,
            echo=settings.app_debug,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

        # ── Task Queue ────────────────────────────────────────────────────────
        from src.infrastructure.task_queue.factory import build_task_queue
        self.task_queue: ITaskQueue = build_task_queue(settings.task_queue)

        # ── Chroma (lazy async init — не можна await в __init__) ─────────────
        # Клієнт будується при першому виклику _get_chroma()
        self._chroma_client = None

        logger.info("Container initialized")

    # ── DB Session ────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager: відкриває сесію + транзакцію.
        Commit — автоматично після yield.
        Rollback — при будь-якому виключенні.

        Використання:
            async with container.db_session() as session:
                result = await container.some_uc(session).execute(...)
            # ← тут commit або rollback
        """
        async with self._session_factory() as session:
            async with session.begin():
                yield session

    # ── Chroma ────────────────────────────────────────────────────────────────

    async def _get_chroma(self):
        """Lazy init Chroma клієнта."""
        if self._chroma_client is None:
            from src.infrastructure.vector_store.chroma_client import build_chroma_client
            self._chroma_client = build_chroma_client()
        return self._chroma_client

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Закрити всі з'єднання при shutdown."""
        await self._engine.dispose()
        if self._chroma_client is not None:
            from src.infrastructure.vector_store.chroma_client import close_chroma
            await close_chroma()
        logger.info("Container closed")

    # ══════════════════════════════════════════════════════════════════════════
    # ФАБРИЧНІ МЕТОДИ — USE CASES
    # Конвенція: {дія}_uc(session) → UseCase
    # session передається ззовні — роутер контролює lifecycle транзакції
    # ══════════════════════════════════════════════════════════════════════════

    # ── Sources ───────────────────────────────────────────────────────────────

    def add_source_uc(self, session: AsyncSession):
        from src.application.use_cases.add_source import AddSourceUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return AddSourceUseCase(
            source_repo=SqlAlchemySourceRepository(session),
        )

    def list_sources_uc(self, session: AsyncSession):
        from src.application.use_cases.list_sources import ListSourcesUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return ListSourcesUseCase(
            source_repo=SqlAlchemySourceRepository(session),
        )

    def deactivate_source_uc(self, session: AsyncSession):
        from src.application.use_cases.deactivate_source import DeactivateSourceUseCase
        from src.infrastructure.persistence.repositories.source_repo import SqlAlchemySourceRepository
        return DeactivateSourceUseCase(
            source_repo=SqlAlchemySourceRepository(session),
        )

    # ── Articles ──────────────────────────────────────────────────────────────

    def list_articles_uc(self, session: AsyncSession):
        from src.application.use_cases.list_articles import ListArticlesUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return ListArticlesUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def get_article_uc(self, session: AsyncSession):
        from src.application.use_cases.get_article import GetArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return GetArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def submit_feedback_uc(self, session: AsyncSession):
        from src.application.use_cases.submit_feedback import SubmitFeedbackUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.infrastructure.persistence.repositories.feed_repo import (
            SqlAlchemyFeedbackRepository, SqlAlchemyFeedRepository,
        )
        return SubmitFeedbackUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            feedback_repo=SqlAlchemyFeedbackRepository(session),
            feed_repo=SqlAlchemyFeedRepository(session),   # для інвалідації snapshot
        )

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
        return MarkArticleReadUseCase(
            feed_repo=SqlAlchemyFeedRepository(session),
        )

    # ── Health ────────────────────────────────────────────────────────────────

    def article_repo(self, session: AsyncSession):
        """Прямий доступ до репозиторію для healthcheck."""
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return SqlAlchemyArticleRepository(session)

    # ── Vector Store (async factory) ──────────────────────────────────────────

    async def article_vector_repo(self):
        """
        ArticleVectorRepository — async factory (потребує await).

        Використання:
            repo = await container.article_vector_repo()
            await repo.upsert(embedding)
        """
        from src.infrastructure.vector_store.article_vector_repo import ArticleVectorRepository
        client = await self._get_chroma()
        return ArticleVectorRepository(client)

    async def criteria_vector_repo(self):
        """CriteriaVectorRepository — async factory."""
        from src.infrastructure.vector_store.criteria_vector_repo import CriteriaVectorRepository
        client = await self._get_chroma()
        return CriteriaVectorRepository(client)

    def create_article_uc(self, session: AsyncSession):
        from src.application.use_cases.create_article import CreateArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return CreateArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def update_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import UpdateArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return UpdateArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def delete_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import DeleteArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return DeleteArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def tag_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import TagArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return TagArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def expire_article_uc(self, session: AsyncSession):
        from src.application.use_cases.update_article import ExpireArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        return ExpireArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )

    def filter_article_uc(self, session: AsyncSession, scoring_service=None):
        """
        FilterArticleUseCase потребує IScoringService.
        Якщо scoring_service=None — передати NoOpScoringService або
        EmbeddingsScoringService з infrastructure.
        """
        from src.application.use_cases.filter_article import FilterArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.config.settings import get_settings

        if scoring_service is None:
            # fallback — заглушка поки embedding pipeline не реалізовано
            from src.infrastructure.scoring.noop_scoring import NoOpScoringService
            scoring_service = NoOpScoringService()

        cfg = get_settings()
        return FilterArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            scoring_service=scoring_service,
            threshold=cfg.filtering.default_threshold,
        )

# ── Singleton ─────────────────────────────────────────────────────────────────

_container: Container | None = None


def init_container() -> Container:
    """Одноразова ініціалізація. Викликати в lifespan."""
    global _container
    _container = Container()
    return _container


def get_container() -> Container:
    """FastAPI Depends та workers використовують цей геттер."""
    if _container is None:
        raise RuntimeError(
            "Container not initialized. Call init_container() in lifespan first."
        )
    return _container