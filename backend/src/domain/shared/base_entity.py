# domain/shared/base_entity.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from .events import DomainEvent

@dataclass
class BaseEntity:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
    

@dataclass
class AggregateRoot(BaseEntity):
    """Aggregate roots збирають domain events і очищають їх після commit."""
    _domain_events: list[DomainEvent] = field(default_factory=list, repr=False)

    def _record_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._domain_events = self._domain_events, []
        return events