# domain/knowledge/events.py
from dataclasses import dataclass, field
from uuid import UUID
from domain.shared.events import DomainEvent


@dataclass(frozen=True)
class ArticleSaved(DomainEvent):
    url: str = ""
    score: float = 0.0

@dataclass(frozen=True)
class ArticleTagged(DomainEvent):
    tag_names: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class EmbeddingStored(DomainEvent):
    embedding_id: UUID = None   # type: ignore[assignment]

@dataclass(frozen=True)
class ArticleExpired(DomainEvent):
    pass