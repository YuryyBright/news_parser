# domain/feed/exceptions.py
from src.domain.shared.exceptions import DomainException

from uuid import UUID


class FeedNotFound(DomainException): pass
class StaleSnapshot(DomainException): pass


class SourceNotFoundError(Exception):
    """Source не знайдено. Presentation → HTTP 404."""
    def __init__(self, source_id: UUID) -> None:
        super().__init__(f"Source '{source_id}' not found")
        self.source_id = source_id