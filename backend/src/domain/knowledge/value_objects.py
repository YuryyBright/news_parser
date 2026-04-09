# domain/knowledge/value_objects.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from src.domain.shared.base_value_object import ValueObject
from src.domain.shared.exceptions import ValidationError
from uuid import UUID

class ArticleStatus(StrEnum):
    PENDING  = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED  = "expired"


@dataclass(frozen=True)
class ContentHash(ValueObject):
    value: str  # sha256 від title+body

    def _validate(self) -> None:
        if len(self.value) != 64:
            raise ValidationError("ContentHash must be sha256 hex string (64 chars)")


@dataclass(frozen=True)
class PublishedAt(ValueObject):
    value: datetime

    def age_hours(self, now: datetime) -> float:
        return (now - self.value).total_seconds() / 3600


@dataclass(frozen=True)
class ArticleFilter(ValueObject):
    """
    Value Object для фільтрації статей.

    Зміна відносно попередньої версії:
      + tag: str | None  — фільтр по тегу тепер є частиною доменного VO,
        а не сирим аргументом що передається напряму в інфраструктурний репозиторій.
        Роутер більше не звертається до SqlAlchemy-репо напряму.
    """
    status: ArticleStatus | None = None
    min_score: float = 0.0
    language: str | None = None
    tag: str | None = None          # ← новий domaine-level фільтр
    limit: int = 50
    tag: str | None = None                           # Додано сюди
    exclude_disliked_by_user: UUID | None = None     # Замість просто user_id для зрозумілості
    offset: int = 0
    date_from: datetime | None = None
    date_to: datetime | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    sort_by: str = "created_at"     # created_at | published_at | relevance_score
    sort_dir: str = "desc"          # asc | desc

    def _validate(self) -> None:
        if not 0.0 <= self.min_score <= 1.0:
            raise ValidationError(f"min_score must be in [0,1], got {self.min_score}")
        if self.limit < 1 or self.limit > 301:
            raise ValidationError(f"limit must be in [1,200], got {self.limit}")
        if self.offset < 0:
            raise ValidationError(f"offset must be >= 0, got {self.offset}")
        if self.sort_by not in ("created_at", "published_at", "relevance_score"):
            raise ValidationError(f"invalid sort_by: {self.sort_by}")
        if self.sort_dir not in ("asc", "desc"):
            raise ValidationError(f"invalid sort_dir: {self.sort_dir}")