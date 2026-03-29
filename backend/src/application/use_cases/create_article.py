# application/use_cases/create_article.py
"""
CreateArticleUseCase — створити статтю напряму (адмін / тест).

В нормальному flow статті надходять через ingestion pipeline.
Цей UC — для адмін-API та тестів.

DDD:
  - ContentHash генерується тут (application coord.) або в domain factory
  - Перевірка дубліката — через domain exception DuplicateArticle
  - Стан починається з PENDING (domain default)
"""
from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from src.application.dtos.article_dto import ArticleDetailView, CreateArticleCommand
from src.domain.knowledge.entities import Article
from src.domain.knowledge.exceptions import DuplicateArticle
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import (
    ArticleStatus, ContentHash, Language, PublishedAt,
)


class CreateArticleUseCase:

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, cmd: CreateArticleCommand) -> ArticleDetailView:
        # 1. Обчислити хеш (dedup)
        content_hash = _compute_hash(cmd.title, cmd.body)

        # 2. Перевірити дублікат за хешем
        existing = await self._repo.get_by_hash(content_hash)
        if existing is not None:
            raise DuplicateArticle(cmd.url)

        # 3. Перевірити дублікат за URL
        existing_url = await self._repo.get_by_url(cmd.url)
        if existing_url is not None:
            raise DuplicateArticle(cmd.url)

        # 4. Побудувати aggregate
        try:
            language = Language(cmd.language)
        except ValueError:
            language = Language.UNKNOWN

        article = Article(
            id=uuid4(),
            source_id=cmd.source_id,
            title=cmd.title,
            body=cmd.body,
            url=cmd.url,
            language=language,
            status=ArticleStatus.PENDING,
            relevance_score=0.0,
            content_hash=ContentHash(value=content_hash),
            published_at=PublishedAt(value=cmd.published_at) if cmd.published_at else None,
        )

        # 5. Persist
        await self._repo.save(article)

        return ArticleDetailView(
            id=article.id,
            title=article.title,
            body=article.body,
            url=article.url,
            language=article.language.value,
            status=article.status.value,
            relevance_score=article.relevance_score,
            published_at=article.published_at.value if article.published_at else None,
            created_at=article.created_at,
            tags=[],
            source_id=article.source_id,
        )


def _compute_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()
