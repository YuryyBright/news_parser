# domain/filtering/events.py
from dataclasses import dataclass
from uuid import UUID
from domain.shared.events import DomainEvent


@dataclass(frozen=True)
class ArticleFiltered(DomainEvent):
    article_id: UUID = None     # type: ignore[assignment]
    score: float = 0.0
    passed: bool = False
    method: str = "hybrid"

@dataclass(frozen=True)
class CriteriaGenerated(DomainEvent):
    user_profile_id: UUID = None  # type: ignore[assignment]
    phrase_count: int = 0
    model_version: str = ""

@dataclass(frozen=True)
class FeedbackRecorded(DomainEvent):
    liked: bool = False
    new_prior: float = 0.5

@dataclass(frozen=True)
class ThresholdUpdated(DomainEvent):
    old_value: float = 0.0
    new_value: float = 0.0