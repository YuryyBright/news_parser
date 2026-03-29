# application/use_cases/update_article.py
"""
Набір use cases для мутацій статті:
  - UpdateArticleUseCase  — редагувати текстові поля
  - TagArticleUseCase     — додати/оновити теги
  - ExpireArticleUseCase  — позначити як застарілу

Всі state transitions — виключно через методи aggregate.
Use case ніколи не пише в поля aggregate напряму.
"""
from __future__ import annotations

from uuid import UUID

from src.application.dtos.article_dto import (
    ArticleDetailView,
    ExpireArticleCommand,
    TagArticleCommand,
    UpdateArticleCommand,
)
from src.domain.knowledge.entities import Tag
from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import Language


# ── Update текстових полів ────────────────────────────────────────────────────

class UpdateArticleUseCase:
    """
    Оновлює редаговані поля: title, body, language.
    
    Статус і score НЕ можна міняти тут —
    вони міняються через FilterArticleUseCase (state machine).
    """

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, cmd: UpdateArticleCommand) -> ArticleDetailView:
        article = await self._repo.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        # Мутуємо тільки передані поля
        if cmd.title is not None:
            article.title = cmd.title
        if cmd.body is not None:
            article.body = cmd.body
        if cmd.language is not None:
            try:
                article.language = Language(cmd.language)
            except ValueError:
                article.language = Language.UNKNOWN

        await self._repo.update(article)

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
            tags=[t.name for t in article.tags],
            source_id=article.source_id,
        )


# ── Теги ──────────────────────────────────────────────────────────────────────

class TagArticleUseCase:
    """
    Додає теги до статті через aggregate метод add_tags().
    Метод сам дедуплікує — повторні теги ігноруються.
    Доменна подія ArticleTagged випускається всередині aggregate.
    """

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, cmd: TagArticleCommand) -> list[str]:
        article = await self._repo.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        new_tags = [Tag(name=name.lower().strip()) for name in cmd.tag_names if name.strip()]
        article.add_tags(new_tags)

        await self._repo.update(article)

        return [t.name for t in article.tags]


# ── Expire ────────────────────────────────────────────────────────────────────

class ExpireArticleUseCase:
    """
    Позначає статтю як EXPIRED через aggregate метод expire().
    Доменна подія ArticleExpired випускається всередині aggregate.
    
    Зазвичай викликається з worker'а за розкладом
    (expire all accepted older than N hours).
    """

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, cmd: ExpireArticleCommand) -> None:
        article = await self._repo.get(cmd.article_id)
        if article is None:
            raise ArticleNotFound(cmd.article_id)

        article.expire()
        await self._repo.update(article)


# ── Delete ────────────────────────────────────────────────────────────────────

class DeleteArticleUseCase:
    """
    Hard delete. Використовувати обережно — краще expire().
    Soft delete (is_deleted) не реалізовано в поточній схемі.
    """

    def __init__(self, article_repo: IArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, article_id: UUID) -> None:
        article = await self._repo.get(article_id)
        if article is None:
            raise ArticleNotFound(article_id)
        await self._repo.delete(article_id)
