# domain/ingestion/value_objects.py
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime
from src.domain.shared.base_value_object import ValueObject


class SourceType(StrEnum):
    TELEGRAM  = "telegram"
    RSS       = "rss"
    WEB       = "web"
    API       = "api"


@dataclass(frozen=True)
class SourceConfig(ValueObject):
    url: str
    source_type: SourceType
    fetch_interval_seconds: int = 300
    headers: dict | None = None  # ← було: dict = None


@dataclass(frozen=True)
class ParsedContent(ValueObject):
    title: str
    body: str
    url: str
    published_at: datetime | None
    language: str | None   # ISO 639-1, None = detect later

    def full_text(self) -> str:
        return f"{self.title}\n{self.body}"


@dataclass(frozen=True)
class FetchSchedule(ValueObject):
    interval_seconds: int
    max_retries: int = 3
    backoff_factor: float = 2.0