# domain/ingestion/exceptions.py
from src.domain.shared.exceptions import DomainException

class ParseError(DomainException): pass
class SourceUnreachable(DomainException): pass
class RateLimitExceeded(DomainException):
    def __init__(self, source_id: object, retry_after: int):
        super().__init__(f"Rate limited for source {source_id}, retry in {retry_after}s")
        self.retry_after = retry_after