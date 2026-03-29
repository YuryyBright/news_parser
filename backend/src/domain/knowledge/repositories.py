# domain/knowledge/repositories.py
from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.shared.base_repository import IRepository
from .entities import Article, ArticleEmbedding, Tag
from .value_objects import ArticleStatus, Language


class IArticleRepository(IRepository[Article]):
    @abstractmethod
    async def get_by_url(self, url: str) -> Article | None: ...

    @abstractmethod
    async def list_accepted(
        self,
        limit: int = 50,
        offset: int = 0,
        language: Language | None = None,
    ) -> list[Article]: ...

    @abstractmethod
    async def list_expired_before(self, cutoff: datetime) -> list[Article]: ...


class IArticleEmbeddingRepository(IRepository[ArticleEmbedding]):
    @abstractmethod
    async def get_by_article_id(self, article_id: UUID) -> ArticleEmbedding | None: ...


class ITagRepository(IRepository[Tag]):
    @abstractmethod
    async def get_or_create(self, name: str) -> Tag: ...

    @abstractmethod
    async def list_all(self) -> list[Tag]: ...