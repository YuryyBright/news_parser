# domain/feed/exceptions.py
from domain.shared.exceptions import DomainException

class FeedNotFound(DomainException): pass
class StaleSnapshot(DomainException): pass