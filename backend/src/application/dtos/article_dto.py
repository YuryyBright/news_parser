# application/dtos/article_dto.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ArticleView:
    id: UUID
    title: str
    url: str
    language: str
    status: str
    relevance_score: float
    published_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class SubmitFeedbackCommand:
    user_id: UUID
    article_id: UUID
    liked: bool


@dataclass(frozen=True)
class ListArticlesQuery:
    status: str | None = None
    min_score: float = 0.0
    limit: int = 50
    offset: int = 0