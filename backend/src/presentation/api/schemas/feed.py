from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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


class FeedResponse(BaseModel):
    snapshot_id: UUID
    generated_at: datetime
    items: list[FeedArticleResponse]