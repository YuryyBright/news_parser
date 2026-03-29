# domain/ingestion/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from src.domain.shared.base_entity import BaseEntity, AggregateRoot
from .value_objects import SourceConfig, ParsedContent, FetchSchedule
from .events import ArticleIngested, FetchJobFailed


class FetchJobStatus(StrEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"


@dataclass
class Source(AggregateRoot):
    """
    Aggregate root для джерела новин.
    Знає як себе конфігурувати і чи активне воно.
    """
    name: str = ""
    config: SourceConfig = None  # type: ignore[assignment]
    schedule: FetchSchedule = field(default_factory=lambda: FetchSchedule(300))
    is_active: bool = True

    def disable(self) -> None:
        self.is_active = False

    def update_config(self, config: SourceConfig) -> None:
        self.config = config


@dataclass
class RawArticle(AggregateRoot):
    """
    Aggregate root — стаття одразу після парсингу, до фільтрації.
    Містить сирі дані без будь-якої обробки.
    """
    source_id: UUID = None      # type: ignore[assignment]
    content: ParsedContent = None  # type: ignore[assignment]

    def mark_ingested(self) -> None:
        self._record_event(ArticleIngested(
            aggregate_id=self.id,
            source_id=self.source_id,
            url=self.content.url,
        ))


@dataclass
class FetchJob(BaseEntity):
    source_id: UUID = None      # type: ignore[assignment]
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

    def fail(self, reason: str, max_retries: int = 3) -> None:
        self.retries += 1
        self.error_message = reason
        self.status = (
            FetchJobStatus.FAILED if self.retries >= max_retries
            else FetchJobStatus.PENDING
        )