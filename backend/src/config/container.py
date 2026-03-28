# infrastructure/config/container.py
"""
DI-контейнер — єдине місце де збираються всі залежності.

Infrastructure знає про:
- свої реалізації (репозиторії, сервіси)
- application.ports (інтерфейси)

НЕ знає про: FastAPI internals, presentation layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from functools import cached_property

from src.config.settings import Settings, get_settings
from infrastructure.persistence.database import AsyncSessionFactory
from infrastructure.task_queue.background_queue import InMemoryTaskQueue
from application.ports import ITaskQueue


@dataclass
class Container:
    settings: Settings = field(default_factory=get_settings)

    # ── Task Queue ──────────────────────────────────────────────────────────
    @cached_property
    def task_queue(self) -> ITaskQueue:
        """
        Dev: InMemoryTaskQueue (asyncio background tasks)
        Prod: замінити на CeleryTaskQueue — той самий інтерфейс ITaskQueue
        """
        if self.settings.task_queue.use_celery:
            from infrastructure.task_queue.celery_queue import CeleryTaskQueue
            return CeleryTaskQueue(self.settings.task_queue)
        return InMemoryTaskQueue()

    # ── Session factory ─────────────────────────────────────────────────────
    def make_session(self):
        """Повертає async context manager для сесії."""
        return AsyncSessionFactory()

    # ── Repository factories (session передається ззовні для UoW) ──────────
    def source_repo(self, session):
        from infrastructure.persistence.repositories.source_repo import SourceRepository
        return SourceRepository(session)

    def raw_article_repo(self, session):
        from infrastructure.persistence.repositories.raw_article_repo import RawArticleRepository
        return RawArticleRepository(session)

    def article_repo(self, session):
        from infrastructure.persistence.repositories.article_repo import ArticleRepository
        return ArticleRepository(session)

    def fetch_job_repo(self, session):
        from infrastructure.persistence.repositories.fetch_job_repo import FetchJobRepository
        return FetchJobRepository(session)


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container