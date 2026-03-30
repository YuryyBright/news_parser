# infrastructure/persistence/repositories/raw_article_repo.py
"""
SqlAlchemyRawArticleRepository — реалізує IRawArticleRepository.

Mapper розгортає ParsedContent ↔ плоскі колонки ORM моделі.
Domain entity ніколи не знає про структуру БД.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.entities import RawArticle, RawArticleStatus
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.persistence.models import RawArticleModel


class SqlAlchemyRawArticleRepository(IRawArticleRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── IRepository (base) ────────────────────────────────────────────────────

    async def get(self, id: UUID) -> RawArticle | None:
        model = await self._session.get(RawArticleModel, str(id))
        return _to_domain(model) if model else None

    async def save(self, entity: RawArticle) -> None:
        existing = await self._session.get(RawArticleModel, str(entity.id))
        if existing:
            _update_model(existing, entity)
        else:
            self._session.add(_to_model(entity))
        await self._session.flush()

    async def update(self, entity: RawArticle) -> None:
        await self.save(entity)

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(RawArticleModel, str(id))
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def list(self) -> list[RawArticle]:
        result = await self._session.execute(select(RawArticleModel))
        return [_to_domain(m) for m in result.scalars().all()]

    # ── IRawArticleRepository (specific) ─────────────────────────────────────

    async def exists_by_url(self, url: str) -> bool:
        result = await self._session.execute(
            select(RawArticleModel.id).where(RawArticleModel.url == url).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_hash(self, content_hash: str) -> bool:
        result = await self._session.execute(
            select(RawArticleModel.id)
            .where(RawArticleModel.content_hash == content_hash)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_unprocessed(self, limit: int = 100) -> list[RawArticle]:
        result = await self._session.execute(
            select(RawArticleModel)
            .where(RawArticleModel.status == RawArticleStatus.PENDING.value)
            .order_by(RawArticleModel.created_at)
            .limit(limit)
        )
        return [_to_domain(m) for m in result.scalars().all()]

    async def mark_processed(self, id: UUID) -> None:
        await self._set_status(id, RawArticleStatus.PROCESSED)

    async def mark_deduplicated(self, id: UUID) -> None:
        await self._set_status(id, RawArticleStatus.DEDUPLICATED)

    async def mark_invalid(self, id: UUID) -> None:
        await self._set_status(id, RawArticleStatus.INVALID)

    async def _set_status(self, id: UUID, status: RawArticleStatus) -> None:
        model = await self._session.get(RawArticleModel, str(id))
        if model:
            model.status = status.value
            await self._session.flush()


# ── Mapper functions ──────────────────────────────────────────────────────────

def _to_model(entity: RawArticle) -> RawArticleModel:
    """
    RawArticle → RawArticleModel.

    ParsedContent розгортається у плоскі колонки ORM —
    бо реляційна БД не знає про value objects.
    """
    return RawArticleModel(
        id=str(entity.id),
        source_id=str(entity.source_id) if entity.source_id else None,
        title=entity.content.title,
        body=entity.content.body,
        url=entity.content.url,
        language=entity.content.language,
        published_at=entity.content.published_at,
        content_hash=entity.content_hash,     # із ParsedContent.content_hash
        status=entity.processing_status.value,
    )


def _update_model(model: RawArticleModel, entity: RawArticle) -> None:
    """Оновити існуючу ORM модель з domain entity."""
    model.status = entity.processing_status.value
    # title/body/url/hash не змінюються після створення


def _to_domain(model: RawArticleModel) -> RawArticle:
    """
    RawArticleModel → RawArticle.

    Плоскі колонки збираються назад у ParsedContent.
    """
    content = ParsedContent(
        title=model.title,
        body=model.body,
        url=model.url,
        published_at=model.published_at,
        language=model.language,
    )
    return RawArticle(
        id=UUID(model.id),
        source_id=UUID(model.source_id) if model.source_id else None,
        content=content,
        processing_status=RawArticleStatus(model.status),
    )