
# domain/knowledge/value_objects.py
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime
from src.domain.shared.base_value_object import ValueObject
from src.domain.shared.exceptions import ValidationError


class ArticleStatus(StrEnum):
    PENDING   = "pending"    # пройшов dedup, чекає фільтрації
    ACCEPTED  = "accepted"   # пройшов фільтр
    REJECTED  = "rejected"   # не пройшов фільтр
    EXPIRED   = "expired"    # старіший за retention window




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
    
    # domain/knowledge/value_objects.py  (додати)
@dataclass(frozen=True)
class ArticleFilter:
    """Query object — параметри вибірки статей."""
    status: ArticleStatus | None = None
    min_score: float = 0.0
    language: str | None = None
    limit: int = 50
    offset: int = 0

    def _validate(self) -> None:
        if not 0.0 <= self.min_score <= 1.0:
            raise ValidationError(f"min_score must be in [0,1], got {self.min_score}")
        if self.limit < 1 or self.limit > 200:
            raise ValidationError(f"limit must be in [1,200], got {self.limit}")
        if self.offset < 0:
            raise ValidationError(f"offset must be a non-negative integer, got {self.offset}")