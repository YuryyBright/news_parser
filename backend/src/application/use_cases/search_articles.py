# application/use_cases/search_articles.py
"""
SearchArticlesUseCase — full-text пошук по title + body.

DDD-правила:
  ✅ залежить від порту IArticleRepository (не від ORM)
  ✅ повертає DTO ArticleView — не доменну сутність
  ✅ знання про PostgreSQL tsvector/tsquery знаходиться ВИКЛЮЧНО
     в SqlAlchemyArticleRepository.full_text_search() — не тут

Раніше: логіка пошуку жила у роутері articles.py (DDD-порушення —
  presentation layer звертався до SqlAlchemyArticleRepository напряму).
Тепер:  роутер викликає цей use case через container.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.article_dto import ArticleView
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleStatus
from src.application.use_cases.list_articles import _to_view


@dataclass(frozen=True)
class SearchArticlesQuery:
    query: str
    language: str | None = None
    status: ArticleStatus | None = None
    limit: int = 20


@dataclass
class SearchArticlesResult:
    query: str
    total: int
    items: list[ArticleView]


class SearchArticlesUseCase:
    """
    Full-text пошук статей.

    Делегує реальну роботу репозиторію через порт IArticleRepository.
    Порт містить метод full_text_search() — SqlAlchemy-імплементація
    використовує tsvector/tsquery, in-memory — simple scan.
    """

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, q: SearchArticlesQuery) -> SearchArticlesResult:
        articles = await self._repo.full_text_search(
            query=q.query,
            language=q.language,
            status=q.status,
            limit=q.limit,
        )
        views = [_to_view(a) for a in articles]
        return SearchArticlesResult(
            query=q.query,
            total=len(views),
            items=views,
        )