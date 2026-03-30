# application/ports/scoring_service.py
from abc import ABC, abstractmethod
from src.domain.ingestion.value_objects import ParsedContent

class IScoringService(ABC):
    @abstractmethod
    async def score(self, content: ParsedContent) -> float: ...  # 0.0 – 1.0