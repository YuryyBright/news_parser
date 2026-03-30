# domain/knowledge/repositories.py
"""
Порти (interfaces) домену Knowledge.

Правило DDD:
  Інтерфейс живе в ДОМЕНІ, реалізація — в infrastructure.
  Use cases залежать тільки від цих абстракцій.

ВАЖЛИВО: get_by_hash, count_by_status є в SqlAlchemyArticleRepository,
тому вони МАЮ бути задекларовані тут — інакше порт і адаптер розходяться.
"""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.shared.base_repository import IRepository
from .entities import Article, ArticleEmbedding, Tag
from .value_objects import ArticleStatus, ArticleFilter


class IArticleRepository(IRepository[Article]):

    @abstractmethod
    async def get_by_url(self, url: str) -> Article | None: ...

    @abstractmethod
    async def get_by_hash(self, content_hash: str) -> Article | None: ...

    @abstractmethod
    async def list_accepted(
        self,
        limit: int = 50,
        offset: int = 0,
        language: str | None = None,
    ) -> list[Article]: ...

    @abstractmethod
    async def list_by_status(
        self,
        status: str | None = None,
        min_score: float = 0.0,
        limit: int = 50,
    ) -> list[Article]: ...

    @abstractmethod
    async def list_expired_before(self, cutoff: datetime) -> list[Article]: ...

    @abstractmethod
    async def count_by_status(self) -> dict[str, int]: ...

    @abstractmethod
    async def find(self, filter: ArticleFilter) -> list[Article]: ...


class IArticleEmbeddingRepository(IRepository[ArticleEmbedding]):
    @abstractmethod
    async def get_by_article_id(self, article_id: UUID) -> ArticleEmbedding | None: ...


class ITagRepository(IRepository[Tag]):
    @abstractmethod
    async def get_or_create(self, name: str) -> Tag: ...

    @abstractmethod
    async def list_all(self) -> list[Tag]: ...
