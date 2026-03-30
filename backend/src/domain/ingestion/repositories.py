# domain/ingestion/repositories.py
"""
Інтерфейси репозиторіїв для ingestion bounded context.

Визначаються в domain — реалізуються в infrastructure.
Application знає тільки про ці інтерфейси.
"""
from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from src.domain.ingestion.entities import FetchJob, RawArticle, Source
from src.domain.shared.base_repository import IRepository


class ISourceRepository(IRepository[Source]):
    @abstractmethod
    async def list_active(self) -> list[Source]: ...

    @abstractmethod
    async def get_by_url(self, url: str) -> Source | None:
        """Потрібен для перевірки унікальності при додаванні джерела."""
        ...


class IRawArticleRepository(IRepository[RawArticle]):
    @abstractmethod
    async def exists_by_url(self, url: str) -> bool: ...

    @abstractmethod
    async def exists_by_hash(self, content_hash: str) -> bool: ...

    @abstractmethod
    async def get_unprocessed(self, limit: int = 100) -> list[RawArticle]: ...

    @abstractmethod
    async def mark_processed(self, id: UUID) -> None: ...


class IFetchJobRepository(IRepository[FetchJob]):
    @abstractmethod
    async def get_pending(self, limit: int = 10) -> list[FetchJob]: ...

    @abstractmethod
    async def get_by_source_id(self, source_id: UUID) -> FetchJob | None: ...
