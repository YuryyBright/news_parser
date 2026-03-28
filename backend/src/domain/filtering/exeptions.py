# domain/filtering/exceptions.py
from uuid import UUID
from domain.shared.exceptions import DomainException


class ColdStartRequired(DomainException):
    def __init__(self, profile_id: UUID):
        super().__init__(
            f"No embeddings for profile {profile_id}. Run cold start first."
        )

class InvalidThreshold(DomainException): pass

class EmbeddingDimensionMismatch(DomainException):
    def __init__(self, expected: int, got: int):
        super().__init__(f"Expected {expected}d embedding, got {got}d")