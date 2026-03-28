# domain/filtering/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID
import numpy as np

from domain.shared.base_entity import AggregateRoot, BaseEntity
from .value_objects import EmbeddingVector, RelevanceScore, SignalWeights
from .events import CriteriaGenerated, FeedbackRecorded, ThresholdUpdated
from domain.shared.exceptions import ValidationError


@dataclass
class FilterCriteria(AggregateRoot):
    """
    Aggregate root — вся конфігурація фільтрації одного профілю.

    Cold start: phrase_embeddings is None → потрібна LLM-генерація.
    Warm start: phrase_embeddings заповнені → використовуємо cosine similarity.
    """
    user_profile_id: UUID = None        # type: ignore[assignment]

    # Семантичні критерії (embedding-based)
    phrases: list[str] = field(default_factory=list)
    phrase_embeddings: np.ndarray | None = field(default=None, repr=False)

    # Точні критерії (keyword-based)
    keywords: list[str] = field(default_factory=list)

    # Персоналізація
    threshold: float = 0.40
    feedback_prior: float = 0.50       # Beta prior, починається нейтрально
    feedback_count: int = 0

    # Мовний фільтр ([] = приймаємо будь-яку мову)
    allowed_languages: list[str] = field(default_factory=list)

    weights: SignalWeights = field(default_factory=SignalWeights)

    def is_cold_start(self) -> bool:
        return self.phrase_embeddings is None or len(self.phrase_embeddings) == 0

    def set_phrase_embeddings(
        self, embeddings: np.ndarray, model_version: str
    ) -> None:
        if len(embeddings) != len(self.phrases):
            raise ValidationError(
                f"Got {len(embeddings)} embeddings for {len(self.phrases)} phrases"
            )
        self.phrase_embeddings = embeddings
        self._record_event(CriteriaGenerated(
            aggregate_id=self.id,
            user_profile_id=self.user_profile_id,
            phrase_count=len(self.phrases),
            model_version=model_version,
        ))

    def record_feedback(self, liked: bool) -> None:
        """Байєсівський апдейт Beta(α, β) prior."""
        self.feedback_count += 1
        # Накопичуємо в prior, не перезаписуємо
        alpha = 1 + (self.feedback_prior * self.feedback_count) + (1 if liked else 0)
        beta  = 1 + ((1 - self.feedback_prior) * self.feedback_count) + (0 if liked else 1)
        self.feedback_prior = round(alpha / (alpha + beta), 4)
        self._record_event(FeedbackRecorded(
            aggregate_id=self.id,
            liked=liked,
            new_prior=self.feedback_prior,
        ))

    def update_threshold(self, value: float) -> None:
        if not 0.0 < value < 1.0:
            raise ValidationError(f"Threshold must be in (0, 1), got {value}")
        old = self.threshold
        self.threshold = value
        self._record_event(ThresholdUpdated(
            aggregate_id=self.id,
            old_value=old,
            new_value=value,
        ))


@dataclass
class UserProfile(BaseEntity):
    name: str = ""
    criteria_id: UUID | None = None


@dataclass
class RelevanceFeedback(BaseEntity):
    article_id: UUID = None     # type: ignore[assignment]
    criteria_id: UUID = None    # type: ignore[assignment]
    liked: bool = False
    score_at_feedback: float = 0.0