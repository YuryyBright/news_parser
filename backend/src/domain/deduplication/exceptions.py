# domain/deduplication/exceptions.py
"""
Доменні виключення для ingestion pipeline.

Ієрархія:
  DomainException
    └── IngestionException
          ├── DuplicateContentError      ← exact hash match
          ├── NearDuplicateContentError  ← MinHash similarity
          └── InvalidContentError        ← валідація контенту

Use cases ловлять ці виключення і вирішують:
  - DuplicateContentError      → позначити raw як "deduplicated", skip
  - NearDuplicateContentError  → те саме, але логувати similarity score
  - InvalidContentError        → позначити raw як "invalid", skip
"""
from __future__ import annotations

from uuid import UUID

from src.domain.shared.exceptions import DomainException


class IngestionException(DomainException):
    """Base для всього ingestion домену."""


class DuplicateContentError(IngestionException):
    """
    Exact duplicate: sha256 хеш вже існує в системі.

    existing_id — ID вже існуючої статті (RawArticle або Article).
    """
    def __init__(
        self,
        content_hash: str,
        existing_id: UUID,
        existing_table: str = "raw_articles",
    ) -> None:
        self.content_hash = content_hash
        self.existing_id = existing_id
        self.existing_table = existing_table
        super().__init__(
            f"Duplicate content (hash={content_hash[:8]}...) "
            f"already exists in {existing_table} as {existing_id}"
        )


class NearDuplicateContentError(IngestionException):
    """
    Near-duplicate: MinHash Jaccard similarity перевищує threshold.

    similarity ∈ [0.0, 1.0], де 1.0 = ідентичний текст.
    """
    def __init__(
        self,
        similarity: float,
        threshold: float,
        existing_id: UUID,
    ) -> None:
        self.similarity = similarity
        self.threshold = threshold
        self.existing_id = existing_id
        super().__init__(
            f"Near-duplicate content (similarity={similarity:.3f} >= threshold={threshold}) "
            f"matches existing article {existing_id}"
        )


class InvalidContentError(IngestionException):
    """Контент не пройшов базову валідацію (порожній, занадто короткий тощо)."""
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid content: {reason}")
