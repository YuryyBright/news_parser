# application/dtos/article_dto.py
"""
DTOs та команди для домену Article.

Правило:
  - *View — незмінний read-model для presentation
  - *Command — вхідна команда для use case (write-side)
  - *Query  — параметри фільтрації (read-side)

DTOs НЕ містять доменної логіки.
DTOs НЕ знають про ORM і HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


# ── Read models (View) ────────────────────────────────────────────────────────

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
    user_liked: bool | None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArticleDetailView(ArticleView):
    """Розширена view з тілом статті — для GET /articles/{id}."""
    body: str = ""
    source_id: UUID | None = None


# ── Commands (Write-side) ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class CreateArticleCommand:
    """
    Команда для створення статті вручну (напр. через адмін-API).
    Нормальний шлях — через ingestion pipeline.
    """
    source_id: UUID
    title: str
    body: str
    url: str
    language: str = "unknown"
    published_at: datetime | None = None


@dataclass(frozen=True)
class UpdateArticleCommand:
    """
    Оновлення редагованих полів статті.
    Статус і score змінюються тільки через state-machine методи aggregate.
    """
    article_id: UUID
    title: str | None = None
    body: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class AcceptArticleCommand:
    """Перевести статтю в статус ACCEPTED з оцінкою релевантності."""
    article_id: UUID
    relevance_score: float


@dataclass(frozen=True)
class RejectArticleCommand:
    """Перевести статтю в статус REJECTED."""
    article_id: UUID
    relevance_score: float = 0.0


@dataclass(frozen=True)
class ExpireArticleCommand:
    """Позначити статтю як застарілу (EXPIRED)."""
    article_id: UUID


@dataclass(frozen=True)
class TagArticleCommand:
    """Додати теги до статті."""
    article_id: UUID
    tag_names: list[str]


@dataclass(frozen=True)
class SubmitFeedbackCommand:
    user_id: UUID
    article_id: UUID
    liked: bool


# ── Queries (Read-side filters) ───────────────────────────────────────────────

@dataclass(frozen=True)
class ListArticlesQuery:
    status: str | None = None
    min_score: float = 0.0
    language: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetArticleQuery:
    article_id: UUID
