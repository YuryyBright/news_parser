# application/use_cases/get_article.py
"""
GetArticleUseCase — отримати одну статтю за ID.

DDD-правила:
  ✅ залежить від порту (IArticleRepository), не від ORM
  ✅ повертає DTO (ArticleDetailView), не доменну сутність
  ✅ кидає доменний виняток ArticleNotFound — роутер перехоплює його
"""
from __future__ import annotations

from uuid import UUID

from src.application.dtos.article_dto import ArticleDetailView
from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository


class GetArticleUseCase:

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, article_id: UUID) -> ArticleDetailView:
        article = await self._repo.get(article_id)

        if article is None:
            raise ArticleNotFound(article_id)

        return ArticleDetailView(
            id=article.id,
            title=article.title,
            body=article.body,
            url=article.url,
            language=article.language,
            status=article.status.value,
            relevance_score=article.relevance_score,
            published_at=article.published_at.value if article.published_at else None,
            created_at=article.created_at,
            tags=[t.name for t in article.tags],
            source_id=article.source_id,
        )
