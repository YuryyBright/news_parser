# domain/feed/events.py
from dataclasses import dataclass
from uuid import UUID
from domain.shared.events import DomainEvent


@dataclass(frozen=True)
class FeedGenerated(DomainEvent):
    user_id: UUID = None        # type: ignore[assignment]
    item_count: int = 0

@dataclass(frozen=True)
class ArticleRead(DomainEvent):
    user_id: UUID = None        # type: ignore[assignment]
    article_id: UUID = None     # type: ignore[assignment]

@dataclass(frozen=True)
class ArticleSaved(DomainEvent):
    user_id: UUID = None        # type: ignore[assignment]
    article_id: UUID = None     # type: ignore[assignment]

@dataclass(frozen=True)
class NotificationSent(DomainEvent):
    user_id: UUID = None        # type: ignore[assignment]
    channel: str = ""