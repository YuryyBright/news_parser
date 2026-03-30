# domain/ingestion/entities.py
"""
Агрегати домену Ingestion.

Source      — джерело новин (RSS, Web, API, Telegram)
RawArticle  — стаття одразу після парсингу, до обробки Knowledge доменом
FetchJob    — журнал одного запуску fetcher'а для джерела
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from src.domain.shared.base_entity import AggregateRoot, BaseEntity
from .value_objects import SourceConfig, ParsedContent, FetchSchedule
from .events import ArticleIngested, FetchJobFailed


class FetchJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


class RawArticleStatus(StrEnum):
    """
    Статус raw article в ingestion pipeline.

    PENDING       → щойно збережено, чекає обробки
    PROCESSED     → Knowledge domain створив Article з цього raw
    DEDUPLICATED  → виявлено дублікат, Article не створювався
    INVALID       → контент не пройшов валідацію
    """
    PENDING      = "pending"
    PROCESSED    = "processed"
    DEDUPLICATED = "deduplicated"
    INVALID      = "invalid"


@dataclass
class Source(AggregateRoot):
    """Aggregate root для джерела новин."""
    name: str = ""
    config: SourceConfig = None         # type: ignore[assignment]
    schedule: FetchSchedule = field(default_factory=lambda: FetchSchedule(300))
    is_active: bool = True

    @property
    def url(self) -> str:
        return self.config.url if self.config else ""

    def disable(self) -> None:
        self.is_active = False

    def update_config(self, config: SourceConfig) -> None:
        self.config = config


@dataclass
class RawArticle(AggregateRoot):
    """
    Aggregate root для сирої статті.

    ID призначається при створенні (uuid4) — до збереження в БД.
    content_hash обчислюється з ParsedContent, а не ззовні —
    щоб уникнути розбіжностей між fetcher'ом і use case.
    processing_status відстежує де стаття знаходиться в pipeline.
    """
    source_id: UUID = None              # type: ignore[assignment]
    content: ParsedContent = None       # type: ignore[assignment]
    processing_status: RawArticleStatus = RawArticleStatus.PENDING

    def __post_init__(self) -> None:
        # Гарантуємо що id завжди є — навіть до збереження в БД
        if self.id is None:
            self.id = uuid4()

    @property
    def content_hash(self) -> str:
        """
        Хеш делегується до ParsedContent — єдине місце обчислення.
        Fetcher'и і use cases не рахують хеш самі.
        """
        return self.content.content_hash if self.content else ""

    def mark_ingested(self) -> None:
        """Записує доменну подію після успішного збереження."""
        self._record_event(ArticleIngested(
            aggregate_id=self.id,
            source_id=self.source_id,
            url=self.content.url,
        ))

    def mark_processed(self) -> None:
        """Knowledge domain успішно створив Article."""
        self.processing_status = RawArticleStatus.PROCESSED

    def mark_deduplicated(self) -> None:
        """Виявлено дублікат — Article не буде створено."""
        self.processing_status = RawArticleStatus.DEDUPLICATED

    def mark_invalid(self) -> None:
        """Контент не пройшов валідацію."""
        self.processing_status = RawArticleStatus.INVALID


@dataclass
class FetchJob(BaseEntity):
    """
    Запис одного запуску fetcher'а для джерела.
    Дозволяє відстежувати re-fetch, кількість помилок, причину.
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
            else FetchJobStatus.PENDING
        )
        self._record_event(FetchJobFailed(
            aggregate_id=self.id,
            source_id=self.source_id,
            reason=reason,
            retries=self.retries,
        ))