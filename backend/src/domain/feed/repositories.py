# domain/feed/repositories.py
from abc import abstractmethod
from uuid import UUID
from domain.shared.base_repository import IRepository
from .entities import FeedSnapshot, ReadHistory, Notification


class IFeedSnapshotRepository(IRepository[FeedSnapshot]):
    @abstractmethod
    async def get_latest(self, user_id: UUID) -> FeedSnapshot | None: ...

    @abstractmethod
    async def invalidate_for_user(self, user_id: UUID) -> None: ...


class IReadHistoryRepository(IRepository[ReadHistory]):
    @abstractmethod
    async def get_read_ids(self, user_id: UUID) -> set[UUID]: ...


class INotificationRepository(IRepository[Notification]):
    @abstractmethod
    async def list_pending(self, limit: int = 100) -> list[Notification]: ...