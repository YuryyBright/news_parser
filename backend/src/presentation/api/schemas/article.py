# presentation/api/schemas/article.py
"""
Pydantic schemas — виключно для HTTP шару.

Правило:
  ✅ Schemas не знають про domain entities і DTOs
  ✅ Роутер конвертує schema → command/query → передає в use case
  ❌ Ніякої бізнес-логіки тут
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


# ── Responses ─────────────────────────────────────────────────────────────────

class ArticleResponse(BaseModel):
    id: UUID
    title: str
    url: str
    language: str
    status: str
    relevance_score: float
    published_at: datetime | None
    created_at: datetime
    tags: list[str] = []


class ArticleDetailResponse(ArticleResponse):
    """Повна відповідь з тілом — для GET /articles/{id}."""
    body: str
    source_id: UUID | None = None


# ── Requests ──────────────────────────────────────────────────────────────────

class ArticleCreateRequest(BaseModel):
    source_id: UUID
    title: str = Field(..., min_length=1, max_length=1000)
    body: str = Field(..., min_length=1)
    url: AnyHttpUrl
    language: str | None = None
    published_at: datetime | None = None


class ArticleUpdateRequest(BaseModel):
    """
    PATCH: всі поля опціональні.
    Передаєш тільки те, що хочеш змінити.
    """
    title: str | None = Field(default=None, min_length=1, max_length=1000)
    body: str | None = None
    language: str | None = None


class TagsAddRequest(BaseModel):
    tags: list[str] = Field(..., min_length=1, max_length=20)


class TagsResponse(BaseModel):
    tags: list[str]


class FeedbackCreateRequest(BaseModel):
    user_id: UUID
    liked: bool


class FeedbackResponse(BaseModel):
    status: str
    liked: bool
