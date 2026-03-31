# domain/feed/services.py
from __future__ import annotations
import math
from datetime import datetime, timezone
from uuid import UUID

from src.domain.knowledge.entities import Article
from .entities import FeedItem, FeedSnapshot
from .value_objects import UserPreference


class FeedRankingService:
    """
    Ранжування статей для фіду.
    Формула: final_rank = relevance_score * recency_factor * diversity_penalty
    """

    def build_snapshot(
        self,
        user_id: UUID,
        articles: list[Article],
        preference: UserPreference,
        read_article_ids: set[UUID],
    ) -> FeedSnapshot:
        scored = [
            (a, self._score(a, preference))
            for a in articles
            if a.id not in read_article_ids
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        items = [
            FeedItem(article_id=a.id, rank=i, score=round(s, 4))
            for i, (a, s) in enumerate(scored[: preference.max_items_per_feed])
        ]
        return FeedSnapshot.create(user_id=user_id, items=items)

    def _score(self, article: Article, preference: UserPreference) -> float:
        base = article.relevance_score

        # Recency decay: score * e^(-age / decay_hours)
        if article.published_at:
            now = datetime.now(timezone.utc)
            age_h = article.published_at.age_hours(now)
            decay = math.exp(-age_h / max(preference.recency_decay_hours, 1))
        else:
            decay = 0.8  # невідомий вік — невеликий штраф

        return base * decay