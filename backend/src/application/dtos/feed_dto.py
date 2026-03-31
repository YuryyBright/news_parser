# application/dtos/feed_dto.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FeedItemView:
    id: UUID
    article_id: UUID
    rank: int
    score: float
    status: str                       # "unread" | "read"
    article_title: str
    article_url: str
    article_relevance_score: float
    article_published_at: datetime | None


@dataclass(frozen=True)
class FeedSnapshotView:
    
    id: UUID
    user_id: UUID
    generated_at: datetime
    items: list[FeedItemView] = field(default_factory=list)


@dataclass(frozen=True)
class BuildFeedCommand:
    user_id: UUID
    force_rebuild: bool = False       # ігнорувати кеш і зібрати новий snapshot


@dataclass(frozen=True)
class MarkArticleReadCommand:
    user_id: UUID
    article_id: UUID