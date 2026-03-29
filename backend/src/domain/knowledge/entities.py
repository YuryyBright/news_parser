# domain/knowledge/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID
import numpy as np

from domain.shared.base_entity import AggregateRoot, BaseEntity
from .value_objects import ArticleStatus, ContentHash, Language, PublishedAt
from .events import ArticleSaved, ArticleTagged, EmbeddingStored, ArticleExpired


@dataclass
class Tag(BaseEntity):
    name: str = ""
    source: str = "auto"  # "auto" | "user"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Tag):
            return False
        return self.name.lower() == other.name.lower()

    def __hash__(self) -> int:
        return hash(self.name.lower())


@dataclass
class ArticleEmbedding(BaseEntity):
    article_id: UUID = None         # type: ignore[assignment]
    vector: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    model_version: str = ""
    dimensions: int = 384


@dataclass
class Article(AggregateRoot):
    """
    Aggregate root домену Knowledge.
    Відповідає за весь lifecycle статті після фільтрації.
    """
    source_id: UUID = None          # type: ignore[assignment]
    raw_article_id: UUID | None = None
    title: str = ""
    body: str = ""
    url: str = ""
    language: Language = Language.UNKNOWN
    status: ArticleStatus = ArticleStatus.PENDING
    relevance_score: float = 0.0
    content_hash: ContentHash = None  # type: ignore[assignment]
    published_at: PublishedAt | None = None
    tags: list[Tag] = field(default_factory=list)
    embedding_id: UUID | None = None

    # --- стан-машина ---
    def accept(self, score: float) -> None:
        self.status = ArticleStatus.ACCEPTED
        self.relevance_score = score
        self._record_event(ArticleSaved(
            aggregate_id=self.id,
            url=self.url,
            score=score,
        ))

    def reject(self, score: float) -> None:
        self.status = ArticleStatus.REJECTED
        self.relevance_score = score

    def expire(self) -> None:
        self.status = ArticleStatus.EXPIRED
        self._record_event(ArticleExpired(aggregate_id=self.id))

    def attach_embedding(self, embedding_id: UUID) -> None:
        self.embedding_id = embedding_id
        self._record_event(EmbeddingStored(
            aggregate_id=self.id,
            embedding_id=embedding_id,
        ))

    def add_tags(self, tags: list[Tag]) -> None:
        new = [t for t in tags if t not in self.tags]
        self.tags.extend(new)
        if new:
            self._record_event(ArticleTagged(
                aggregate_id=self.id,
                tag_names=[t.name for t in new],
            ))

    @property
    def full_text(self) -> str:
        return f"{self.title}\n{self.body}"

    def is_accepted(self) -> bool:
        return self.status == ArticleStatus.ACCEPTED