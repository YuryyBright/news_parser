# application/use_cases/list_articles.py
"""
ListArticlesUseCase — read-only query (CQRS Query).

Зміна відносно попередньої версії:
  - Фільтр по тегу тепер передається через ArticleFilter.tag,
    а не окремим аргументом прямо в SqlAlchemy-репо з роутера.
  - _to_view коректно розгортає PublishedAt VO → datetime.
  - Повертає ArticleView DTO — не доменну сутність Article.
  - [НОВЕ] user_id передається в execute() щоб:
      а) виключати дизлайкнуті статті
      б) збагачувати DTO полем user_liked (None | True | False)
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.dtos.article_dto import ArticleView
from src.domain.knowledge.entities import Article
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleFilter


class ListArticlesUseCase:
    """Повертає перелік статей з підтримкою фільтрів, пагінації та сортування."""

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(
        self,
        filter: ArticleFilter,
        user_id: UUID | None = None,
    ) -> list[ArticleView]:
        """
        Args:
            filter:  стандартний фільтр (статус, мова, score, пагінація).
            user_id: якщо переданий —
                       • виключає статті, які цей юзер дизлайкнув
                       • заповнює ArticleView.user_liked (True/False/None)
        """
        articles = await self._repo.find(filter, user_id=user_id)

        if user_id is None:
            return [_to_view(a) for a in articles]

        # Збагачуємо: отримуємо feedback одним запитом
        article_ids = [a.id for a in articles]
        feedback_map = await self._repo.get_feedback_map(
            user_id=user_id,
            article_ids=article_ids,
        )
        return [_to_view(a, liked=feedback_map.get(a.id)) for a in articles]

    async def count(self, filter: ArticleFilter) -> int:
        return await self._repo.count(filter)


# ── Presentation mapper ────────────────────────────────────────────────────────

def _to_view(article: Article, liked: bool | None = None) -> ArticleView:
    """
    Перетворює Article aggregate → ArticleView DTO.

    PublishedAt — Value Object; розгортаємо .value щоб DTO не тягнув
    доменні типи у presentation layer.

    Args:
        liked: None  — feedback відсутній (ще не оцінено)
               True  — стаття лайкнута
               False — стаття дизлайкнута (зазвичай не з'явиться у списку,
                       але може бути присутня в /preferences endpoint)
    """
    published_at: datetime | None = None
    if article.published_at is not None:
        published_at = (
            article.published_at.value
            if hasattr(article.published_at, "value")
            else article.published_at
        )

    return ArticleView(
        id=article.id,
        title=article.title,
        url=article.url,
        language=article.language,
        status=article.status.value,
        relevance_score=article.relevance_score,
        published_at=published_at,
        created_at=article.created_at,
        tags=[t.name for t in article.tags],
        user_liked=liked,           # ← нове поле
    )