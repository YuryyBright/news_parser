# infrastructure/persistence/repositories/article_repo.py
"""
SqlAlchemyArticleRepository — реалізує IArticleRepository.

Знає про: domain interface, ORM models, mapper.
НЕ знає про: use cases, FastAPI, Pydantic, Chroma.

Зміни:
  [НОВЕ] get_feedback_map() — батч-запит liked/disliked для списку статей.
         Повертає dict[UUID, bool] — ключ = article_id, значення = liked.
         Використовується в ListArticlesUseCase для збагачення DTO.

  [FIX]  find() — user_id більше не опціональний kwargs, а явний параметр
         щоб уникнути signature mismatch з інтерфейсом.
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
        user_id: UUID | None = None,
    ) -> list[Article]:
        """
        Загальний пошук статей.

        Args:
            filter:  фільтри (включно з filter.tag), пагінація, сортування.
            user_id: якщо переданий — виключає статті, які цей юзер дизлайкнув.
        """
        from src.infrastructure.persistence.models import UserFeedbackModel

        stmt = (
            select(ArticleModel)
            .options(selectinload(ArticleModel.tags))
            .offset(filter.offset)
            .limit(filter.limit)
        )

        # Застосовуємо всі фільтри (включно з tag, date, sort) через централізовану функцію
        tag = getattr(filter, "tag", None)
        stmt = _apply_filters_to_stmt(stmt, ArticleModel, filter, tag)

        # ВИКЛЮЧЕННЯ ДИЗЛАЙКНУТИХ — один підзапит
        if user_id is not None:
            disliked_subquery = (
                select(UserFeedbackModel.article_id)
                .where(
                    and_(
                        UserFeedbackModel.user_id == str(user_id),
                        UserFeedbackModel.liked == False,   # noqa: E712
                    )
                )
            ).scalar_subquery()
            stmt = stmt.where(ArticleModel.id.not_in(disliked_subquery))

        result = await self._session.execute(stmt)
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

    # ─── [НОВЕ] Feedback map ──────────────────────────────────────────────────

    async def get_feedback_map(
        self,
        user_id: UUID,
        article_ids: list[UUID],
    ) -> dict[UUID, bool]:
        """
        Батч-запит: повертає liked/disliked для списку статей.

        Один SQL замість N запитів у циклі.

        Returns:
            {article_id: liked} — тільки статті, де feedback існує.
            Статті без feedback — відсутні в словнику (caller обробляє як None).

        Використання в ListArticlesUseCase:
            feedback_map = await repo.get_feedback_map(user_id, article_ids)
            liked = feedback_map.get(article.id)   # None якщо не оцінено
        """
        if not article_ids:
            return {}

        from src.infrastructure.persistence.models import UserFeedbackModel

        result = await self._session.execute(
            select(UserFeedbackModel.article_id, UserFeedbackModel.liked)
            .where(
                and_(
                    UserFeedbackModel.user_id == str(user_id),
                    UserFeedbackModel.article_id.in_([str(aid) for aid in article_ids]),
                )
            )
        )
        return {UUID(row.article_id): row.liked for row in result.all()}

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

        expired_result = await self._session.execute(
            select(func.count(ArticleModel.id))
            .where(ArticleModel.status == "expired")
        )
        counts["expired"] = expired_result.scalar_one() or 0
        return counts

    async def count(self, f: ArticleFilter, tag: str | None = None) -> int:
        """Підрахунок загальної кількості статей для пагінації."""
        stmt = select(func.count()).select_from(ArticleModel)
        stmt = _apply_filters_to_stmt(stmt, ArticleModel, f, tag)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def full_text_search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        language: str | None = None,
        status: ArticleStatus | None = None,
    ) -> list[Article]:
        from src.infrastructure.persistence.models import ArticleModel
        from sqlalchemy import func, select, or_

        dialect_name = self._session.bind.dialect.name

        stmt = select(ArticleModel).options(selectinload(ArticleModel.tags))

        if dialect_name == "sqlite":
            search_term = f"%{query}%"
            stmt = stmt.where(
                or_(
                    ArticleModel.title.ilike(search_term),
                    ArticleModel.body.ilike(search_term),
                )
            )
            stmt = stmt.order_by(ArticleModel.relevance_score.desc())
        else:
            pg_config = _pg_config(language)
            safe_query = _sanitize_tsquery(query)
            if not safe_query:
                return []

            vector = func.to_tsvector(
                pg_config,
                func.coalesce(ArticleModel.title, "") + " " + func.coalesce(ArticleModel.body, ""),
            )
            ts_query = func.plainto_tsquery(pg_config, safe_query)
            stmt = stmt.where(vector.op("@@")(ts_query))
            rank_expr = func.ts_rank(vector, ts_query)
            stmt = stmt.order_by(rank_expr.desc(), ArticleModel.relevance_score.desc())

        if status is not None:
            stmt = stmt.where(ArticleModel.status == status.value)
        if language:
            stmt = stmt.where(ArticleModel.language == language)

        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [ArticleMapper.to_domain(m) for m in result.scalars().all()]

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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _apply_filters_to_stmt(stmt, model, f: ArticleFilter, tag: str | None = None):
    """
    Централізована функція застосування фільтрів.
    Використовується в find() і count().
    """
    from sqlalchemy import and_

    conditions = []

    if f.status is not None:
        conditions.append(model.status == f.status.value)

    if f.min_score and f.min_score > 0:
        conditions.append(model.relevance_score >= f.min_score)

    if f.language:
        conditions.append(model.language == f.language)

    date_from = getattr(f, "date_from", None)
    date_to   = getattr(f, "date_to", None)
    if date_from:
        conditions.append(model.created_at >= date_from)
    if date_to:
        conditions.append(model.created_at <= date_to)

    published_from = getattr(f, "published_from", None)
    published_to   = getattr(f, "published_to", None)
    if published_from:
        conditions.append(model.published_at >= published_from)
    if published_to:
        conditions.append(model.published_at <= published_to)

    if tag:
        from src.infrastructure.persistence.models import TagModel
        stmt = stmt.join(TagModel).where(TagModel.name == tag)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    sort_by  = getattr(f, "sort_by",  "created_at")
    sort_dir = getattr(f, "sort_dir", "desc")

    sort_col = {
        "created_at":      model.created_at,
        "published_at":    model.published_at,
        "relevance_score": model.relevance_score,
    }.get(sort_by, model.created_at)

    if sort_dir == "asc":
        stmt = stmt.order_by(sort_col.asc().nullslast())
    else:
        stmt = stmt.order_by(sort_col.desc().nullsfirst())

    return stmt


def _pg_config(language: str | None) -> str:
    mapping = {
        "en": "english", "de": "german", "fr": "french",
        "es": "spanish", "it": "italian", "pt": "portuguese",
        "nl": "dutch", "ru": "russian", "sk": "slovak", "hu": "hungarian", "ro": "romanian",
    }
    return mapping.get(language or "", "simple")


def _sanitize_tsquery(query: str) -> str:
    import re
    cleaned = re.sub(r"[^\w\s\-]", " ", query, flags=re.UNICODE)
    return " ".join(cleaned.split())