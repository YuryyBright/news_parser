# infrastructure/persistence/repositories/article_repo.py
"""
SqlAlchemyArticleRepository — реалізує IArticleRepository.

Знає про: domain interface, ORM models, mapper.
НЕ знає про: use cases, FastAPI, Pydantic, Chroma.
"""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.knowledge.entities import Article, Tag
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleStatus
from src.infrastructure.persistence.mappers.article_mapper import ArticleMapper
from src.infrastructure.persistence.models import ArticleModel, TagModel, ArticleTagModel

logger = logging.getLogger(__name__)


class SqlAlchemyArticleRepository(IArticleRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── IRepository (base) ───────────────────────────────────────────────────

    async def get(self, id: UUID) -> Article | None:
        model = await self._session.get(
            ArticleModel,
            str(id),
            options=[selectinload(ArticleModel.tags)],
        )
        return ArticleMapper.to_domain(model) if model else None

    async def save(self, article: Article) -> None:
        """Upsert за ID. Теги зберігаються окремо через _sync_tags()."""
        existing = await self._session.get(ArticleModel, str(article.id))
        if existing:
            existing.title           = article.title
            existing.body            = article.body
            existing.url             = article.url
            existing.language        = article.language
            existing.raw_article_id  = article.raw_article_id
            existing.status          = article.status.value
            existing.relevance_score = article.relevance_score
            existing.content_hash    = article.content_hash.value if article.content_hash else ""
            existing.published_at    = article.published_at.value if article.published_at else None
        else:
            model = ArticleMapper.to_model(article)
            self._session.add(model)

        await self._session.flush()
        await self._sync_tags(article)

    async def update(self, article: Article) -> None:
        await self.save(article)

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(ArticleModel, str(id))
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def list(self) -> list[Article]:
        result = await self._session.execute(
            select(ArticleModel).options(selectinload(ArticleModel.tags))
        )
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    # ─── IArticleRepository (specific) ───────────────────────────────────────

    async def get_by_url(self, url: str) -> Article | None:
        result = await self._session.execute(
            select(ArticleModel)
            .where(ArticleModel.url == url)
            .options(selectinload(ArticleModel.tags))
        )
        model = result.scalar_one_or_none()
        return ArticleMapper.to_domain(model) if model else None

    async def get_by_hash(self, content_hash: str) -> Article | None:
        """Пошук за хешем — для дедуплікації на рівні знань."""
        result = await self._session.execute(
            select(ArticleModel)
            .where(ArticleModel.content_hash == content_hash)
            .options(selectinload(ArticleModel.tags))
        )
        model = result.scalar_one_or_none()
        return ArticleMapper.to_domain(model) if model else None

    async def list_accepted(
        self,
        limit: int = 50,
        offset: int = 0,
        language: str | None = None,
    ) -> list[Article]:
        stmt = (
            select(ArticleModel)
            .where(ArticleModel.status == ArticleStatus.ACCEPTED.value)
            .options(selectinload(ArticleModel.tags))
            .order_by(ArticleModel.relevance_score.desc(), ArticleModel.published_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if language:
            stmt = stmt.where(ArticleModel.language == language.value)

        result = await self._session.execute(stmt)
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def list_by_status(
        self,
        status: str | None = None,
        min_score: float = 0.0,
        limit: int = 50,
    ) -> list[Article]:
        """Для list_articles_uc — загальний фільтр."""
        conditions = [ArticleModel.relevance_score >= min_score]
        if status:
            conditions.append(ArticleModel.status == status)

        result = await self._session.execute(
            select(ArticleModel)
            .where(and_(*conditions))
            .options(selectinload(ArticleModel.tags))
            .order_by(ArticleModel.relevance_score.desc())
            .limit(limit)
        )
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def list_expired_before(self, cutoff: datetime) -> list[Article]:
        result = await self._session.execute(
            select(ArticleModel)
            .where(
                and_(
                    ArticleModel.status == ArticleStatus.ACCEPTED.value,
                    ArticleModel.published_at < cutoff,
                )
            )
            .options(selectinload(ArticleModel.tags))
        )
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def count_by_status(self) -> dict[str, int]:
        """Для healthcheck endpoint."""
        result = await self._session.execute(
            select(ArticleModel.status, func.count(ArticleModel.id))
            .group_by(ArticleModel.status)
        )
        return {row[0]: row[1] for row in result.all()}

    # ─── Теги ─────────────────────────────────────────────────────────────────

    async def _sync_tags(self, article: Article) -> None:
        """Синхронізує теги статті: upsert тегів + оновлення зв'язків."""
        if not article.tags:
            return

        for tag in article.tags:
            # get_or_create тегу за іменем
            result = await self._session.execute(
                select(TagModel).where(TagModel.name == tag.name.lower())
            )
            tag_model = result.scalar_one_or_none()
            if not tag_model:
                tag_model = TagModel(name=tag.name.lower(), source=tag.source)
                self._session.add(tag_model)
                await self._session.flush()

            # Додаємо зв'язок якщо ще немає
            existing_link = await self._session.get(
                ArticleTagModel,
                (str(article.id), tag_model.id),
            )
            if not existing_link:
                self._session.add(ArticleTagModel(
                    article_id=str(article.id),
                    tag_id=tag_model.id,
                ))

        await self._session.flush()