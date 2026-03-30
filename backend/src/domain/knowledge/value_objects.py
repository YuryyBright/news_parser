
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