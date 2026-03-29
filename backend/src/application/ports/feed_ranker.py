# application/ports/feed_ranker.py  ← ПОРТ (абстракція)
from abc import ABC, abstractmethod
from uuid import UUID

class IFeedRanker(ABC):
    @abstractmethod
    async def rank(self, user_id: UUID, article_ids: list[UUID]) -> list[tuple[UUID, float]]:
        ...

# infrastructure/ranking/simple_ranker.py  ← РЕАЛІЗАЦІЯ
class ScoreBasedRanker(IFeedRanker):
    async def rank(self, user_id, article_ids):
        ...  # конкретна логіка

# application/use_cases/build_feed.py  ← USE CASE знає тільки про порт
class BuildFeedUseCase:
    def __init__(self, feed_ranker: IFeedRanker):
        self._ranker = feed_ranker  # інтерфейс, не реалізація