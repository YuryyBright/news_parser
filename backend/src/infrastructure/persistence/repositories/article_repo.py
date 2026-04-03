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
from src.domain.knowledge.value_objects import ArticleFilter, ArticleStatus
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
        result = await self._session.execute(
            select(ArticleModel.status, func.count(ArticleModel.id))
            .group_by(ArticleModel.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def find(
        self,
        filter: ArticleFilter,
        tag: str | None = None,
        user_id: UUID | None = None,  # Додаємо user_id як опціональний параметр
    ) -> list[Article]:
        """
        Загальний пошук статей. 
        Якщо передано user_id — виключає статті, які цей юзер дизлайкнув.
        """
        from src.infrastructure.persistence.models import UserFeedbackModel

        # Базові умови
        conditions = [ArticleModel.relevance_score >= filter.min_score]
        
        if filter.status:
            conditions.append(ArticleModel.status == filter.status.value)
        if filter.language:
            conditions.append(ArticleModel.language == filter.language)

        # Основний запит
        stmt = (
            select(ArticleModel)
            .options(selectinload(ArticleModel.tags))
            .order_by(ArticleModel.relevance_score.desc())
            .offset(filter.offset)
            .limit(filter.limit)
        )

        # 1. Фільтрація по тегу (якщо є)
        if tag:
            stmt = (
                stmt
                .join(ArticleTagModel, ArticleTagModel.article_id == ArticleModel.id)
                .join(TagModel, TagModel.id == ArticleTagModel.tag_id)
                .where(TagModel.name == tag.lower().strip())
            )

        # 2. ВИКЛЮЧЕННЯ ДИЗЛАЙКНУТИХ (якщо передано user_id)
        if user_id:
            # Створюємо підзапит для ID статей, які юзер дизлайкнув
            disliked_subquery = (
                select(UserFeedbackModel.article_id)
                .where(
                    and_(
                        UserFeedbackModel.user_id == str(user_id),
                        UserFeedbackModel.liked == False
                    )
                )
            ).scalar_subquery()
            
            # Додаємо умову: ID статті не має бути в списку дизлайкнутих
            conditions.append(ArticleModel.id.not_in(disliked_subquery))

        # Приміняємо всі умови
        stmt = stmt.where(and_(*conditions))

        result = await self._session.execute(stmt)
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def find_by_feedback(
        self,
        user_id: UUID,
        liked: bool,
        limit: int = 100,
    ) -> list[Article]:
        """
        Знайти статті за feedback конкретного юзера.

        liked=True  → статті, які юзер лайкнув ("Вподобані")
        liked=False → статті, які юзер дизлайкнув ("Не подобаються")
        """
        from src.infrastructure.persistence.models import UserFeedbackModel

        result = await self._session.execute(
            select(ArticleModel)
            .join(
                UserFeedbackModel,
                and_(
                    UserFeedbackModel.article_id == ArticleModel.id,
                    UserFeedbackModel.user_id == str(user_id),
                    UserFeedbackModel.liked == liked,
                ),
            )
            .options(selectinload(ArticleModel.tags))
            .order_by(UserFeedbackModel.created_at.desc())
            .limit(limit)
        )
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def count_feedback(self, user_id: UUID) -> dict[str, int]:
        """
        Статистика feedback для юзера:
          { "liked": N, "disliked": M, "expired": K }
        """
        from src.infrastructure.persistence.models import UserFeedbackModel

        result = await self._session.execute(
            select(UserFeedbackModel.liked, func.count(UserFeedbackModel.id))
            .where(UserFeedbackModel.user_id == str(user_id))
            .group_by(UserFeedbackModel.liked)
        )
        rows = result.all()
        counts = {"liked": 0, "disliked": 0}
        for liked_val, count in rows:
            if liked_val:
                counts["liked"] = count
            else:
                counts["disliked"] = count

        # Кількість статей зі статусом "expired" (позначені "не показувати")
        expired_result = await self._session.execute(
            select(func.count(ArticleModel.id))
            .where(ArticleModel.status == "expired")
        )
        counts["expired"] = expired_result.scalar_one() or 0

        return counts

    # ─── Теги ─────────────────────────────────────────────────────────────────

    async def _sync_tags(self, article: Article) -> None:
        if not article.tags:
            return

        for tag in article.tags:
            result = await self._session.execute(
                select(TagModel).where(TagModel.name == tag.name.lower())
            )
            tag_model = result.scalar_one_or_none()
            if not tag_model:
                tag_model = TagModel(name=tag.name.lower(), source=tag.source)
                self._session.add(tag_model)
                await self._session.flush()

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