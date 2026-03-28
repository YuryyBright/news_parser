# domain/ingestion/repositories.py
from abc import abstractmethod
from uuid import UUID
from domain.shared.base_repository import IRepository
from .entities import Source, RawArticle, FetchJob


class ISourceRepository(IRepository[Source]):
    @abstractmethod
    async def list_active(self) -> list[Source]: ...

class IRawArticleRepository(IRepository[RawArticle]):
    @abstractmethod
    async def exists_by_url(self, url: str) -> bool: ...

class IFetchJobRepository(IRepository[FetchJob]):
    @abstractmethod
    async def get_pending(self, limit: int = 10) -> list[FetchJob]: ...