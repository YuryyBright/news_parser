from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ArticleResponse(BaseModel):
    id: UUID
    title: str
    url: str
    language: str
    status: str
    relevance_score: float
    published_at: datetime | None
    created_at: datetime


class FeedbackCreateRequest(BaseModel):
    user_id: UUID
    liked: bool


class FeedbackResponse(BaseModel):
    status: str
    liked: bool