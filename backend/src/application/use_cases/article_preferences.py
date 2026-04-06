# application/use_cases/article_preferences.py
"""
Use cases для вподобань юзера по статтях.

  ListByPreferencesUseCase    — статті, які юзер liked / disliked
  GetPreferencesStatsUseCase  — агрегована статистика (liked_count, disliked_count)

DDD-правила:
  ✅ залежать від IArticleRepository (порт), не від ORM
  ✅ повертають DTO — не доменні сутності
  ✅ роутер більше не імпортує SqlAlchemyArticleRepository напряму

Раніше: обидва endpoints у articles.py звертались до інфраструктури напряму.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.article_dto import ArticleView
from src.domain.knowledge.repositories import IArticleRepository
from src.application.use_cases.list_articles import _to_view


# ─── List by preferences ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ListByPreferencesQuery:
    user_id: UUID
    liked: bool
    limit: int = 100


class ListByPreferencesUseCase:
    """Повертає статті, що відповідають вподобанням юзера."""

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, q: ListByPreferencesQuery) -> list[ArticleView]:
        articles = await self._repo.find_by_feedback(
            user_id=q.user_id,
            liked=q.liked,
            limit=q.limit,
        )
        return [_to_view(a) for a in articles]


# ─── Preferences stats ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GetPreferencesStatsQuery:
    user_id: UUID


@dataclass
class PreferencesStats:
    liked_count: int
    disliked_count: int


class GetPreferencesStatsUseCase:
    """Повертає кількість liked / disliked для юзера."""

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, q: GetPreferencesStatsQuery) -> PreferencesStats:
        counts = await self._repo.count_feedback(user_id=q.user_id)
        # count_feedback повертає dict {"liked": int, "disliked": int}
        return PreferencesStats(
            liked_count=counts.get("liked", 0),
            disliked_count=counts.get("disliked", 0),
        )