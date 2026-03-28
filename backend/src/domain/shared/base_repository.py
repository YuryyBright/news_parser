# domain/shared/base_repository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


class IRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: UUID) -> T | None: ...

    @abstractmethod
    async def save(self, entity: T) -> None: ...

    @abstractmethod
    async def delete(self, id: UUID) -> None: ...
    
    @abstractmethod
    async def update(self, entity: T) -> None: ...

    @abstractmethod
    async def list(self) -> list[T]: ...