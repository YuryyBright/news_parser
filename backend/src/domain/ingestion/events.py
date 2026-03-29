# domain/ingestion/events.py
from dataclasses import dataclass
from uuid import UUID
from src.domain.shared.events import DomainEvent


@dataclass(frozen=True)
class ArticleIngested(DomainEvent):
    source_id: UUID = None      # type: ignore[assignment]
    url: str = ""

@dataclass(frozen=True)
class FetchJobStarted(DomainEvent):
    source_id: UUID = None      # type: ignore[assignment]

@dataclass(frozen=True)
class FetchJobFailed(DomainEvent):
    source_id: UUID = None      # type: ignore[assignment]
    reason: str = ""
    retries: int = 0

@dataclass(frozen=True)
class SourceDisabled(DomainEvent):
    reason: str = ""