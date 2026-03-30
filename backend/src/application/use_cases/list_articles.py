# application/use_cases/list_sources.py
"""
ListArticlesUseCase — read-only query.

У CQRS-стилі це Query, а не Command.
Не модифікує стан — транзакція на запис не потрібна.
"""
from __future__ import annotations

from src.domain.knowledge.value_objects import ArticleFilter
from src.application.dtos.article_dto import ArticleView
from src.domain.knowledge.entities import Article
from src.domain.knowledge.repositories import IArticleRepository


class ListArticlesUseCase:
    """Повертає перелік джерел новин."""

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._articles = article_repo

    async def execute(
        self, 
        filter: ArticleFilter
    ) -> list[ArticleView]:
        articles = await self._articles.find(filter)
        return [_to_view(a) for a in articles]

def _to_view(source: Article) -> ArticleView:
    return ArticleView(
        id=source.id,
        title=source.title,
        url=source.url,
        language=source.language,
        status=source.status.value,
        relevance_score=source.relevance_score,
        published_at=source.published_at,
        created_at=source.created_at,
        tags=source.tags,
    )
