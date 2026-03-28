# domain/filtering/value_objects.py
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
import numpy as np
from domain.shared.base_value_object import ValueObject
from domain.shared.exceptions import ValidationError


class FilterMethod(StrEnum):
    HYBRID    = "hybrid"
    EMBEDDING = "embedding"
    KEYWORD   = "keyword"


@dataclass(frozen=True)
class EmbeddingVector(ValueObject):
    vector: np.ndarray
    model_version: str
    dimensions: int = 384

    def _validate(self) -> None:
        if len(self.vector) != self.dimensions:
            raise ValidationError(
                f"Expected {self.dimensions}d vector, got {len(self.vector)}"
            )

    # numpy arrays не є hashable — потрібен кастомний __hash__
    def __hash__(self) -> int:
        return hash((self.vector.tobytes(), self.model_version))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EmbeddingVector):
            return False
        return (
            self.model_version == other.model_version
            and np.allclose(self.vector, other.vector)
        )


@dataclass(frozen=True)
class RelevanceScore(ValueObject):
    value: float
    emb_component: float = 0.0
    kw_component: float  = 0.0
    fb_component: float  = 0.0
    method: FilterMethod = FilterMethod.HYBRID

    def _validate(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValidationError(f"Score must be in [0,1], got {self.value}")

    @property
    def is_high(self) -> bool:
        return self.value >= 0.7

    @property
    def is_borderline(self) -> bool:
        return 0.35 <= self.value < 0.5


@dataclass(frozen=True)
class SignalWeights(ValueObject):
    embedding: float = 0.60
    keyword: float   = 0.25
    feedback: float  = 0.15

    def _validate(self) -> None:
        total = self.embedding + self.keyword + self.feedback
        if abs(total - 1.0) > 1e-6:
            raise ValidationError(f"Weights must sum to 1.0, got {total}")