# config/container.py
"""
DI Container — збирає граф залежностей.

Lifecycle:
  1. init_container() → ONE TIME in lifespan
  2. await container.init_scoring_pipeline() → ONE TIME in lifespan (async)
  3. get_container()  → роутери та workers

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
from sqlalchemy import text

from src.application.ports.task_queue import ITaskQueue
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class Container:
    """
    Singleton-контейнер залежностей.

    Singleton: engine, session_factory, task_queue, chroma_client,
               embedder, scoring_pipeline
    Per-request: session, репозиторії, use cases

    Lifecycle ініціалізації (lifespan):
        container = init_container()          # sync — engine, task_queue
        await container.init_async()          # async — chroma, scoring pipeline
        ...
        await container.close()               # shutdown
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── SQLAlchemy ────────────────────────────────────────────────────────
        self._engine = create_async_engine(
            settings.database.url,
            echo=settings.app_debug,
            pool_pre_ping=True,
            connect_args={
                "timeout": 30,          
            },
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

        # ── Task Queue ────────────────────────────────────────────────────────
        from src.infrastructure.task_queue.factory import build_task_queue
        self.task_queue: ITaskQueue = build_task_queue(settings.task_queue)

        # ── Async singletons (ініціалізуються в init_async) ──────────────────
        # Chroma
        self._chroma_client = None

        # Scoring pipeline — всі три компоненти зберігаємо окремо,
        # щоб мати прямий доступ де потрібен лише один із них.
        self._composite_scoring = None   # CompositeScoringService
        self._tagger = None              # EmbeddingTagger
        self._profile_learner = None     # ProfileLearner
        self._translator = None          # Translator

        logger.info("Container initialized (sync). Call init_async() to complete setup.")

    # ══════════════════════════════════════════════════════════════════════════
    # ASYNC INITIALIZATION — викликати ONE TIME у lifespan
    # ══════════════════════════════════════════════════════════════════════════

    async def init_async(self) -> None:
        # WAL mode для SQLite (no-op на PostgreSQL)
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA busy_timeout=30000"))
            logger.info("SQLite WAL mode enabled")
        except Exception:
            pass  # не SQLite — ігноруємо

        chroma = await self._get_chroma()
        await self._init_scoring_pipeline(chroma)
        await self._init_translator()
        logger.info("Container.init_async(): done.")
    async def _get_chroma(self):
        """Lazy init Chroma клієнта."""
        if self._chroma_client is None:
            from src.infrastructure.vector_store.chroma_client import build_chroma_client
            self._chroma_client = build_chroma_client()
        return self._chroma_client
    async def _init_translator(self) -> None:
        cfg = get_settings()
        if not cfg.azure_translator.enabled:
            logger.info("Azure Translator disabled (set azure_translator.enabled=true to enable)")
            return
        from src.infrastructure.adapters.azure_translator import AzureTranslatorAdapter
        self._translator = AzureTranslatorAdapter(
            api_key=cfg.azure_translator.api_key,
            region=cfg.azure_translator.region,
            target_language=cfg.azure_translator.target_language,
            skip_languages=cfg.azure_translator.skip_languages,
            endpoint=cfg.azure_translator.endpoint,
        )
        logger.info("Azure Translator initialized (target=%s)", cfg.azure_translator.target_language)

    async def _init_scoring_pipeline(self, chroma_client=None) -> None:
        """
        Збирає весь scoring pipeline і зберігає компоненти як singleton-поля.

        Порядок ініціалізації:
          Embedder
            → EmbeddingTagger
            → InterestProfileRepository (+ chroma)
              → EmbeddingsScoringService
              → ProfileLearner
          BM25ScoringService
          CompositeScoringService (BM25 + Embeddings)
        """
        if self._composite_scoring is not None:
            # Вже ініціалізовано — idempotent
            logger.debug("Scoring pipeline already initialized, skipping.")
            return

        from src.infrastructure.ml.embedder import Embedder
        from src.infrastructure.ml.embedding_tagger import EmbeddingTagger
        from src.infrastructure.scoring.bm25_scoring_service import BM25ScoringService
        from src.infrastructure.scoring.embeddings_scoring_service import EmbeddingsScoringService
        from src.infrastructure.scoring.composite_scoring_service import CompositeScoringService
        from src.infrastructure.scoring.profile_learner import ProfileLearner
        from src.infrastructure.vector_store.interest_profile_repo import InterestProfileRepository
        from src.config.settings import get_settings

        cfg = get_settings()

        logger.info("Loading Embedder model...")
        embedder = Embedder.instance()

        if chroma_client is None:
            chroma_client = await self._get_chroma()

        profile_repo = InterestProfileRepository(client=chroma_client)

        bm25_service = BM25ScoringService()

        embed_service = EmbeddingsScoringService(
            embedder=embedder,
            profile_repo=profile_repo,
        )

        self._composite_scoring = CompositeScoringService(
            bm25=bm25_service,
            embeddings=embed_service,
            bm25_min_threshold=cfg.scoring.bm25_min_threshold,
            bm25_weight=cfg.scoring.bm25_weight,
            embed_weight=cfg.scoring.embed_weight,
            embed_confidence_threshold=cfg.scoring.embed_confidence_threshold, 
        )

        self._tagger = EmbeddingTagger(
            embedder=embedder,
            gap_threshold=cfg.scoring.tagger_threshold,
        )

        self._profile_learner = ProfileLearner(
            embedder=embedder,
            profile_repo=profile_repo,
        )

        logger.info("Scoring pipeline initialized: BM25 + Embeddings composite ready.")

    def _assert_scoring_ready(self) -> None:
        """Перевірка що init_async() було викликано."""
        if self._composite_scoring is None:
            raise RuntimeError(
                "Scoring pipeline not initialized. "
                "Ensure `await container.init_async()` is called in lifespan before serving requests."
            )

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
        async with self._session_factory.begin() as session:
            yield session
    @asynccontextmanager
    async def worker_db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Чиста сесія для воркерів (без автоматичного .begin()).
        Дозволяє робити commit() багато разів без помилок закритого контексту.
        """
        session = self._session_factory()
        try:
            yield session
        finally:
            await session.close()
    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Закрити всі з'єднання при shutdown."""

        if self._translator is not None:
            await self._translator.close()
        await self._engine.dispose()
        if self._chroma_client is not None:
            from src.infrastructure.vector_store.chroma_client import close_chroma
            await close_chroma()
        logger.info("Container closed")

    # ══════════════════════════════════════════════════════════════════════════
    # ФАБРИЧНІ МЕТОДИ — USE CASES
    # Конвенція: {дія}_uc(session) → UseCase
    # session передається ззовні — роутер/worker контролює lifecycle транзакції
    # ══════════════════════════════════════════════════════════════════════════

    # ── Ingestion pipeline ────────────────────────────────────────────────────

    def ingest_source_uc(self, session: AsyncSession):
        """
        IngestSourceUseCase — завантажити сирі статті для одного джерела.
        Використовується в handle_ingest_source worker'і.
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
        Версія для worker'а — кожна стаття обробляється в окремій транзакції.
 
        [ОНОВЛЕНО] Тепер передає dedup_uc для повноцінної MinHash дедуплікації.
        DeduplicateRawArticleUseCase замінює примітивний URL/hash check.
 
        Вимагає попереднього виклику init_async().
        """
        self._assert_scoring_ready()
 
        from src.application.use_cases.process_articles import ProcessArticlesUseCase
        from src.infrastructure.adapters.lang_detect_adapter import LangDetectAdapter
        from src.infrastructure.persistence.repositories.raw_article_repo import SqlAlchemyRawArticleRepository
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.config.settings import get_settings
 
        cfg = get_settings()
 
        def build_raw_repo(session):
            return SqlAlchemyRawArticleRepository(session)
 
        def build_article_repo(session):
            return SqlAlchemyArticleRepository(session)
 
        # ── Dedup UC фабрика ──────────────────────────────────────────────────
        # DeduplicateRawArticleUseCase потребує session → створюємо через closure.
        # process_articles_uc отримує фабрику щоб створювати dedup_uc
        # в рамках тієї самої сесії що й article_repo / raw_repo.
        #
        # ВАЖЛИВО: dedup_uc і репозиторії мають бути в ОДНІЙ сесії —
        # інакше mark_deduplicated не побачить щойно збережені записи.
 
        minhash_repo = self._get_minhash_repo()
 
        def build_dedup_uc(session):
            from src.application.use_cases.deduplicate_article import DeduplicateRawArticleUseCase
            from src.domain.deduplication.services import DeduplicationDomainService
            return DeduplicateRawArticleUseCase(
                raw_repo=SqlAlchemyRawArticleRepository(session),
                article_repo=SqlAlchemyArticleRepository(session),
                minhash_repo=minhash_repo,   # singleton — shared між сесіями
                dedup_service=DeduplicationDomainService(
                    num_perm=cfg.dedup.minhash_num_perm,
                ),
                minhash_threshold=cfg.dedup.minhash_threshold,
            )
 
        return ProcessArticlesUseCase(
            session_factory=self._session_factory,
            raw_repo_factory=build_raw_repo,
            article_repo_factory=build_article_repo,
            language_detector=LangDetectAdapter(),
            scoring_service=self._composite_scoring,
            tagger=self._tagger,
            profile_learner=self._profile_learner,
            dedup_uc_factory=build_dedup_uc,   # ← НОВЕ: фабрика замість інстансу
            threshold=cfg.filtering.default_threshold,
            translator=self._translator,
            target_language=cfg.azure_translator.target_language,
        )

    def startup_uc(self, session: AsyncSession):
        """
        StartupUseCase — поставити всі активні джерела в чергу.
        Використовується в lifespan і handle_schedule_all_sources.
        """
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
        """
        Замінює попередню версію.
        Тепер повертає ListArticlesUseCase з методом count(),
        тому роутер не мусить звертатись до репо напряму для підрахунку.
        """
        from src.application.use_cases.list_articles import ListArticlesUseCase
        from src.infrastructure.persistence.repositories.article_repo import (
            SqlAlchemyArticleRepository,
        )
        return ListArticlesUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )
    def search_articles_uc(self, session: AsyncSession):
        """Full-text пошук — роутер більше не імпортує SqlAlchemy-репо."""
        from src.application.use_cases.search_articles import SearchArticlesUseCase
        from src.infrastructure.persistence.repositories.article_repo import (
            SqlAlchemyArticleRepository,
        )
        return SearchArticlesUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )
    def list_by_preferences_uc(self, session: AsyncSession):
        """Список статей за вподобаннями юзера."""
        from src.application.use_cases.article_preferences import ListByPreferencesUseCase
        from src.infrastructure.persistence.repositories.article_repo import (
            SqlAlchemyArticleRepository,
        )
        return ListByPreferencesUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
        )
    def get_preferences_stats_uc(self, session: AsyncSession):
        """Статистика liked / disliked для юзера."""
        from src.application.use_cases.article_preferences import GetPreferencesStatsUseCase
        from src.infrastructure.persistence.repositories.article_repo import (
            SqlAlchemyArticleRepository,
        )
        return GetPreferencesStatsUseCase(
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
            feed_repo=SqlAlchemyFeedRepository(session),
            profile_learner=self._profile_learner, 
        )

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
        from src.application.use_cases.filter_article import FilterArticleUseCase
        from src.infrastructure.persistence.repositories.article_repo import SqlAlchemyArticleRepository
        from src.config.settings import get_settings

        if scoring_service is None:
            # Якщо pipeline вже ініціалізований — використовуємо composite,
            # інакше fallback на NoOp (для healthcheck / тестів без init_async).
            if self._composite_scoring is not None:
                scoring_service = self._composite_scoring
            else:
                from src.infrastructure.scoring.noop_scoring import NoOpScoringService
                scoring_service = NoOpScoringService()

        cfg = get_settings()
        return FilterArticleUseCase(
            article_repo=SqlAlchemyArticleRepository(session),
            scoring_service=scoring_service,
            threshold=cfg.filtering.default_threshold,
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
        from src.infrastructure.vector_store.article_vector_repo import ArticleVectorRepository
        client = await self._get_chroma()
        return ArticleVectorRepository(client)

    async def criteria_vector_repo(self):
        from src.infrastructure.vector_store.criteria_vector_repo import CriteriaVectorRepository
        client = await self._get_chroma()
        return CriteriaVectorRepository(client)

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _get_minhash_repo(self):
        from src.config.settings import get_settings
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
        from src.config.settings import get_settings

        cfg = get_settings()
        return DeduplicateRawArticleUseCase(
            raw_repo=SqlAlchemyRawArticleRepository(session),
            article_repo=SqlAlchemyArticleRepository(session),
            minhash_repo=self._get_minhash_repo(),
            dedup_service=DeduplicationDomainService(
                num_perm=cfg.dedup.minhash_num_perm,
            ),
            minhash_threshold=cfg.dedup.minhash_threshold,
        )

    def batch_deduplicate_uc(self, session: AsyncSession):
        from src.application.use_cases.deduplicate_article import BatchDeduplicateUseCase
        return BatchDeduplicateUseCase(
            single_uc=self.deduplicate_uc(session),
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_container: Container | None = None


def init_container() -> Container:
    """Одноразова sync-ініціалізація. Викликати в lifespan."""
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