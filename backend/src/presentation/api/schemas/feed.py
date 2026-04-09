# Додати до src/presentation/api/schemas/feed.py

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Literal


class FeedArticleResponse(BaseModel):
    article_id: UUID
    rank: int
    score: float
    status: str
    title: str
    language: str
    url: str
    relevance_score: float
    published_at: datetime | None


class FeedPageResponse(BaseModel):
    """Відповідь з пагінацією — замінює FeedResponse."""
    snapshot_id: UUID
    generated_at: datetime
    total: int
    offset: int
    limit: int
    has_more: bool
    items: list[FeedArticleResponse]


# Залишаємо FeedResponse як alias для зворотної сумісності
FeedResponse = FeedPageResponse