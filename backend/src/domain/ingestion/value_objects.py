# domain/ingestion/value_objects.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime

from src.domain.shared.base_value_object import ValueObject
from src.domain.shared.exceptions import ValidationError


class SourceType(StrEnum):
    TELEGRAM = "telegram"
    RSS      = "rss"
    WEB      = "web"
    API      = "api"


@dataclass(frozen=True)
class SourceConfig(ValueObject):
    url: str
    source_type: SourceType
    fetch_interval_seconds: int = 300
    headers: dict | None = None

    def _validate(self) -> None:
        if not self.url.strip():
            raise ValidationError("SourceConfig.url cannot be empty")
        if self.fetch_interval_seconds < 60:
            raise ValidationError("fetch_interval_seconds must be >= 60")


@dataclass(frozen=True)
class ParsedContent(ValueObject):
    """
    Контент, розпарсений з джерела — ще до збереження.

    Єдина відповідальність: тримати сирі дані та вміти
    обчислювати ContentHash. Хешування живе тут, а не в fetcher'і
    чи use case, бо "ідентичний контент = однаковий хеш" —
    доменний інваріант.
    """
    title: str
    body: str
    url: str
    published_at: datetime | None
    language: str | None        # ISO 639-1, None = detect later

    def _validate(self) -> None:
        if not self.title.strip():
            raise ValidationError("ParsedContent.title cannot be empty")
        if not self.url.strip():
            raise ValidationError("ParsedContent.url cannot be empty")

    def full_text(self) -> str:
        return f"{self.title}\n{self.body}"

    @property
    def content_hash(self) -> str:
        """
        SHA-256 від нормалізованого title+body.
        Нормалізація (lowercase + collapse whitespace) гарантує що
        'Hello  World' і 'hello world' дають однаковий хеш.
        """
        normalized = _normalize(self.title) + "\n" + _normalize(self.body)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FetchSchedule(ValueObject):
    interval_seconds: int
    max_retries: int = 3
    backoff_factor: float = 2.0

    def _validate(self) -> None:
        if self.interval_seconds < 60:
            raise ValidationError("interval_seconds must be >= 60")
        if self.max_retries < 0:
            raise ValidationError("max_retries must be >= 0")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()