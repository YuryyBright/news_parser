# infrastructure/persistence/repositories/raw_article_repo.py
"""
SqlAlchemyRawArticleRepository — реалізує IRawArticleRepository.

Ключова відповідальність: ДЕДУПЛІКАЦІЯ.

Дедуплікація відбувається на двох рівнях:
  1. exists_by_url()  — перевірка за URL (точний збіг)
  2. exists_by_hash() — перевірка за SHA-256 хешем title+body
                        (ловить перевидані матеріали з іншим URL)

Use case викликає обидва методи ПЕРЕД збереженням нової статті.
"""
from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ingestion.entities import RawArticle
from domain.ingestion.repositories import IRawArticleRepository
from infrastructure.persistence.mappers.article_mapper import RawArticleMapper
from infrastructure.persistence.models import RawArticleModel

logger = logging.getLogger(__name__)


class SqlAlchemyRawArticleRepository(IRawArticleRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── IRepository ─────────────────────────────────────────────────────────

    async def get(self, id: UUID) -> RawArticle | None:
        model = await self._session.get(RawArticleModel, str(id))
        return RawArticleMapper.to_domain(model) if model else None

    async def save(self, raw: RawArticle) -> None:
        existing = await self._session.get(RawArticleModel, str(raw.id))
        if existing:
            # RawArticle immutable після ingestion — оновлюємо тільки статус
            existing.status = "pending"
        else:
            self._session.add(RawArticleMapper.to_model(raw))
        await self._session.flush()

    async def update(self, raw: RawArticle) -> None:
        await self.save(raw)

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(RawArticleModel, str(id))
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def list(self) -> list[RawArticle]:
        result = await self._session.execute(select(RawArticleModel))
        return [RawArticleMapper.to_domain(m) for m in result.scalars().all()]

    # ─── IRawArticleRepository ────────────────────────────────────────────────

    async def exists_by_url(self, url: str) -> bool:
        """
        Дедуплікація рівень 1: перевірка за URL.
        Найшвидший метод — унікальний індекс на url в БД.
        """
        stmt = select(exists().where(RawArticleModel.url == url))
        result = await self._session.execute(stmt)
        return result.scalar()

    async def exists_by_hash(self, content_hash: str) -> bool:
        """
        Дедуплікація рівень 2: перевірка за SHA-256 хешем title+body.
        Ловить перевидані матеріали з іншим URL але однаковим контентом.
        """
        stmt = select(exists().where(RawArticleModel.content_hash == content_hash))
        result = await self._session.execute(stmt)
        return result.scalar()

    async def get_unprocessed(self, limit: int = 100) -> list[RawArticle]:
        """
        Повертає сирі статті зі статусом 'pending' для подальшої обробки.
        Використовується в handle_process_articles worker'і.
        """
        result = await self._session.execute(
            select(RawArticleModel)
            .where(RawArticleModel.status == "pending")
            .order_by(RawArticleModel.created_at.asc())
            .limit(limit)
        )
        return [RawArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def mark_processed(self, raw_id: UUID) -> None:
        """Позначити raw article як оброблену (щоб не брати повторно)."""
        model = await self._session.get(RawArticleModel, str(raw_id))
        if model:
            model.status = "processed"
            await self._session.flush()

    # ─── Утиліта ──────────────────────────────────────────────────────────────

    @staticmethod
    def compute_hash(title: str, body: str) -> str:
        """SHA-256 від title+body. Використовувати в use cases перед збереженням."""
        return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()