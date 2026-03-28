# infrastructure/config/container.py
"""
DI-контейнер — єдине місце де збираються всі залежності.
Use cases отримують залежності тут, не через FastAPI Depends.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from functools import cached_property

from infrastructure.config.settings import Settings, get_settings
from infrastructure.persistence.database import AsyncSessionFactory
from infrastructure.persistence.repositories.source_repo import SourceRepository
from infrastructure.persistence.repositories.article_repo import ArticleRepository
from infrastructure.persistence.repositories.criteria_repo import CriteriaRepository
from infrastructure.persistence.repositories.feed_repo import FeedRepository
from infrastructure.persistence.repositories.user_repo import UserRepository
from infrastructure.vector_store.chroma_store import ChromaStore
from infrastructure.ml.embedding_service import EmbeddingService
from infrastructure.ml.llm_service import LLMService
from infrastructure.task_queue.factory import build_task_queue
from application.ports import ITaskQueue


@dataclass
class Container:
    settings: Settings = field(default_factory=get_settings)

    # ── ML Services ────────────────────────────────────────────────────────
    @cached_property
    def embedding_service(self) -> EmbeddingService:
        return EmbeddingService(self.settings.embedding)

    @cached_property
    def llm_service(self) -> LLMService:
        return LLMService(self.settings.llm)

    @cached_property
    def chroma_store(self) -> ChromaStore:
        return ChromaStore(self.settings.chroma, self.settings.vector_dim)

    # ── Task Queue ─────────────────────────────────────────────────────────
    @cached_property
    def task_queue(self) -> ITaskQueue:
        return build_task_queue(self.settings.task_queue)

    # ── Session factory (для use cases поза FastAPI) ───────────────────────
    def make_session(self):
        return AsyncSessionFactory()

    # ── Use Case factories (беруть session ззовні для proper transaction) ──
    def source_repo(self, session) -> SourceRepository:
        return SourceRepository(session)

    def article_repo(self, session) -> ArticleRepository:
        return ArticleRepository(session)

    def criteria_repo(self, session) -> CriteriaRepository:
        return CriteriaRepository(session)

    def feed_repo(self, session) -> FeedRepository:
        return FeedRepository(session)

    def user_repo(self, session) -> UserRepository:
        return UserRepository(session)


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container