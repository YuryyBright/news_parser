# domain/feed/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from domain.shared.base_entity import AggregateRoot, BaseEntity
from .value_objects import FeedItemStatus, UserPreference, NotificationChannel
from .events import FeedGenerated, ArticleRead, ArticleSaved, NotificationSent


@dataclass
class FeedItem(BaseEntity):
    article_id: UUID = None         # type: ignore[assignment]
    rank: int = 0
    score: float = 0.0
    status: FeedItemStatus = FeedItemStatus.UNREAD

    def mark_read(self) -> None:
        self.status = FeedItemStatus.READ

    def save_for_later(self) -> None:
        self.status = FeedItemStatus.SAVED


@dataclass
class FeedSnapshot(AggregateRoot):
    """
    Aggregate root — знімок фіду для конкретного юзера в конкретний момент.
    Іммутабельний після генерації (новий snapshot = новий агрегат).
    """
    user_id: UUID = None            # type: ignore[assignment]
    items: list[FeedItem] = field(default_factory=list)
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_stale: bool = False

    def mark_stale(self) -> None:
        self.is_stale = True

    @classmethod
    def create(cls, user_id: UUID, items: list[FeedItem]) -> "FeedSnapshot":
        snapshot = cls(user_id=user_id, items=items)
        snapshot._record_event(FeedGenerated(
            aggregate_id=snapshot.id,
            user_id=user_id,
            item_count=len(items),
        ))
        return snapshot


@dataclass
class ReadHistory(BaseEntity):
    user_id: UUID = None            # type: ignore[assignment]
    article_id: UUID = None         # type: ignore[assignment]
    read_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    time_spent_seconds: int | None = None


@dataclass
class Notification(BaseEntity):
    user_id: UUID = None            # type: ignore[assignment]
    channel: NotificationChannel = NotificationChannel.NONE
    payload: dict = field(default_factory=dict)
    sent_at: datetime | None = None
    status: str = "pending"         # pending | sent | failed

    def mark_sent(self) -> None:
        self.status = "sent"
        self.sent_at = datetime.now(timezone.utc)

    def mark_failed(self, reason: str) -> None:
        self.status = "failed"
        self.payload["error"] = reason