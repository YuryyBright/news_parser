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
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional


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

class FeedbackStateResponse(BaseModel):
    """Поточний стан feedback для статті."""
    article_id: UUID
    liked: bool | None  # None = не оцінено, True = лайк, False = дизлайк
 
 
class FeedbackResponse(BaseModel):
    """Відповідь після POST feedback."""
    status: str
    action: str        # "added" | "changed" | "removed"
    liked: bool | None  # None якщо скасовано
 

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
    liked: bool | None = None  # ← було bool


class CheckDuplicateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Заголовок статті")
    body: str  = Field(..., min_length=1, description="Текст статті")
 
 
class CheckDuplicateResponse(BaseModel):
    is_duplicate: bool
    reason: Optional[str] = None          # "exact_raw" | "exact_article" | "near_similar"
    existing_id: Optional[UUID] = None    # UUID знайденого дубліката
    similarity: Optional[float] = None    # тільки для near_similar
    content_hash: Optional[str] = None    # sha256 (для діагностики)
 
 
class FindSimilarRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body: str  = Field(default="", description="Текст статті (опціонально)")
    top_n: int = Field(default=5, ge=1, le=50)
    language: Optional[str] = Field(default=None, description="Фільтр мови, напр. 'uk'")
 
 
class SimilarArticleItemResponse(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: Optional[str] = None
    article_id: Optional[UUID] = None
 
 
class FindSimilarResponse(BaseModel):
    query_title: str
    total_found: int
    items: list[SimilarArticleItemResponse]
