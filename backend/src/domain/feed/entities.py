# domain/feed/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.domain.shared.base_entity import AggregateRoot, BaseEntity
from .value_objects import FeedItemStatus, UserPreference, NotificationChannel
from .events import FeedGenerated, ArticleRead, ArticleSaved, NotificationSent

@dataclass
class UserFeedback(BaseEntity):
    user_id: UUID = None            # type: ignore[assignment]
    article_id: UUID = None         # type: ignore[assignment]
    liked: bool = False



@dataclass
class FeedItem(BaseEntity):
    id: UUID = None                # type: ignore[assignment]
    snapshot_id: UUID = None       # type: ignore[assignment]
    article_id: UUID = None         # type: ignore[assignment]
    rank: int = 0
    score: float = 0.0
    status: FeedItemStatus = FeedItemStatus.UNREAD
    language: str = ""
    article_title: str = ""
    article_url: str = ""
    article_published_at: datetime | None = None

    def mark_read(self) -> None:
        self.status = FeedItemStatus.READ

    def save_for_later(self) -> None:
        self.status = FeedItemStatus.SAVED

@dataclass(frozen=True)
class FeedItemRef:
    """
    Легковагове посилання на елемент фіду. 
    Використовується для швидких запитів (наприклад, перевірки статусу), 
    щоб не завантажувати весь FeedSnapshot.
    """
    id: UUID
    status: str  # або FeedItemStatus, якщо маппер це підтримує

@dataclass(kw_only=True)
class FeedSnapshot(AggregateRoot):
    """
    Aggregate root — знімок фіду для конкретного юзера в конкретний момент.
    """
    id: UUID
    user_id: UUID
    items: list[FeedItem] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_stale: bool = False

    def mark_stale(self) -> None:
        """Позначає знімок як неактуальний (наприклад, з'явились нові статті)."""
        self.is_stale = True

    def get_item_by_article(self, article_id: UUID) -> FeedItem | None:
        """Пошук конкретного елемента всередині агрегату."""
        for item in self.items:
            if item.article_id == article_id:
                return item
        return None

    @classmethod
    def create(cls, user_id: UUID, items: list[FeedItem]) -> "FeedSnapshot":
        """Фабричний метод для створення нового фіду."""
        snapshot = cls(id=uuid4(), user_id=user_id, items=items)
        # snapshot._record_event(FeedGenerated(aggregate_id=snapshot.id, user_id=user_id))
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