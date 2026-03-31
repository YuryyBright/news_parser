# domain/feed/repositories.py
from abc import abstractmethod
from uuid import UUID
from src.domain.shared.base_repository import IRepository
from .entities import FeedSnapshot, ReadHistory, Notification, UserFeedback


# src/domain/feed/repositories.py
from abc import ABC, abstractmethod
from uuid import UUID
from .entities import FeedSnapshot
from .entities import FeedItemRef

class IFeedRepository(ABC):
    
    @abstractmethod
    async def get_active_snapshot(self, user_id: UUID) -> FeedSnapshot | None:
        """Повертає найсвіжіший snapshot, де is_stale == False."""
        pass

    @abstractmethod
    async def save_snapshot(self, snapshot: FeedSnapshot) -> None:
        """Зберігає новий агрегат фіду разом з усіма його items."""
        pass

    @abstractmethod
    async def find_active_item(self, user_id: UUID, article_id: UUID) -> FeedItemRef | None:
        """
        Швидко знаходить item у поточному активному фіді юзера.
        Повертає DTO (FeedItemRef), а не всю сутність.
        """
        pass

    @abstractmethod
    async def mark_item_read(self, feed_item_id: UUID) -> None:
        """
        Точковий update статусу. Хоча по-правильному в DDD ми б мали
        змінити статус через snapshot.get_item(...).mark_read() і викликати save_snapshot,
        для перформансу часто роблять такий точковий метод у репозиторії.
        """
        pass

    # @abstractmethod
    # async def invalidate_snapshots(self, user_id: UUID) -> None:
    #     """Позначає всі попередні фіди користувача як is_stale = True."""
    #     pass


class IFeedbackRepository(IRepository):
    @abstractmethod
    async def submit_feedback(self, feedback: UserFeedback) -> None: ...

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