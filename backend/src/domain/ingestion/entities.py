# domain/ingestion/entities.py
"""
Агрегати домену Ingestion.

Source      — джерело новин (RSS, Web, API, Telegram)
RawArticle  — стаття одразу після парсингу, до обробки
FetchJob    — журнал одного запуску fetcher'а для джерела
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from src.domain.shared.base_entity import BaseEntity, AggregateRoot
from .value_objects import SourceConfig, ParsedContent, FetchSchedule
from .events import ArticleIngested, FetchJobFailed


class FetchJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


@dataclass
class Source(AggregateRoot):
    """
    Aggregate root для джерела новин.
    Знає свою конфігурацію та розклад fetching'у.
    """
    name: str = ""
    config: SourceConfig = None         # type: ignore[assignment]
    schedule: FetchSchedule = field(default_factory=lambda: FetchSchedule(300))
    is_active: bool = True

    @property
    def url(self) -> str:
        """Зручний доступ до URL без занурення в config."""
        return self.config.url if self.config else ""

    def disable(self) -> None:
        self.is_active = False

    def update_config(self, config: SourceConfig) -> None:
        self.config = config


@dataclass
class RawArticle(AggregateRoot):
    id: UUID = None
    source_id: UUID = None
    content: ParsedContent = None       # єдине джерело правди
    content_hash: str = ""

    def mark_ingested(self) -> None:
        """Записує доменну подію ArticleIngested."""
        self._record_event(ArticleIngested(
            aggregate_id=self.id,
            source_id=self.source_id,
            url=self.content.url,
        ))


@dataclass
class FetchJob(BaseEntity):
    """
    Запис одного запуску fetcher'а для джерела.

    Дозволяє відстежувати:
      - чи потрібен re-fetch (last_run_at + schedule)
      - кількість невдалих спроб (retries)
      - причину останньої помилки (error_message)
    """
    source_id: UUID = None              # type: ignore[assignment]
    status: FetchJobStatus = FetchJobStatus.PENDING
    retries: int = 0
    last_run_at: datetime | None = None
    error_message: str | None = None

    def start(self) -> None:
        self.status = FetchJobStatus.RUNNING
        self.last_run_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        self.status = FetchJobStatus.DONE
        self.retries = 0
        self.error_message = None

    def fail(self, reason: str, max_retries: int = 3) -> None:
        self.retries += 1
        self.error_message = reason
        self.status = (
            FetchJobStatus.FAILED
            if self.retries >= max_retries
            else FetchJobStatus.PENDING   # pending = можна перезапустити
        )
        self._record_event(FetchJobFailed(
            aggregate_id=self.id,
            source_id=self.source_id,
            reason=reason,
            retries=self.retries,
        ))

    