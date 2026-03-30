# infrastructure/persistence/repositories/raw_article_repo.py
"""
SqlAlchemyRawArticleRepository — реалізує IRawArticleRepository.

Bounded context: INGESTION (не knowledge).
Таблиця: raw_articles

Ключова відповідальність: зберігання та дедуплікація сирих статей.

Дедуплікація на двох рівнях (обидва викликаються в IngestSourceUseCase):
  1. exists_by_url()  — точний збіг URL (швидко, є унікальний індекс)
  2. exists_by_hash() — SHA-256(title+body), ловить перевидані з іншим URL
"""
from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.infrastructure.persistence.mappers.article_mapper import RawArticleMapper  # RawArticleMapper живе в article_mapper.py
from src.infrastructure.persistence.models import RawArticleModel

logger = logging.getLogger(__name__)


class SqlAlchemyRawArticleRepository(IRawArticleRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── IRepository (base) ───────────────────────────────────────────────────

    async def get(self, id: UUID) -> RawArticle | None:
        model = await self._session.get(RawArticleModel, str(id))
        return RawArticleMapper.to_domain(model) if model else None

    async def save(self, raw: RawArticle) -> None:
        """
        Upsert за ID.
        RawArticle після збереження — immutable (не оновлюємо контент).
        При повторному save — оновлюємо тільки статус (на випадок retry).
        """
        existing = await self._session.get(RawArticleModel, str(raw.id))
        if existing:
            existing.status = existing.status  # не змінюємо — лише flush
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

    # ─── IRawArticleRepository (specific) ────────────────────────────────────

    async def exists_by_url(self, url: str) -> bool:
        """
        Дедуплікація рівень 1: перевірка за URL.
        Очікує унікальний індекс на raw_articles.url — O(log n).
        """
        stmt = select(exists().where(RawArticleModel.url == url))
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def exists_by_hash(self, content_hash: str) -> bool:
        """
        Дедуплікація рівень 2: SHA-256 хеш title+body.
        Ловить перевидані матеріали з іншим URL але однаковим контентом.
        Очікує індекс на raw_articles.content_hash.
        """
        stmt = select(exists().where(RawArticleModel.content_hash == content_hash))
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def get_unprocessed(self, limit: int = 100) -> list[RawArticle]:
        """
        Повертає сирі статті зі статусом 'pending'.
        Використовується в ProcessArticlesUseCase.
        Сортування за created_at asc — обробляємо в порядку надходження (FIFO).
        """
        result = await self._session.execute(
            select(RawArticleModel)
            .where(RawArticleModel.status == "pending")
            .order_by(RawArticleModel.created_at.asc())
            .limit(limit)
        )
        return [RawArticleMapper.to_domain(m) for m in result.scalars().all()]

    async def mark_processed(self, raw_id: UUID) -> None:
        """
        Позначити raw article як оброблену.
        Викликається ProcessArticlesUseCase після успішного створення Article.
        """
        model = await self._session.get(RawArticleModel, str(raw_id))
        if model:
            model.status = "processed"
            await self._session.flush()

    # ─── Утиліта ──────────────────────────────────────────────────────────────

    @staticmethod
    def compute_hash(title: str, body: str) -> str:
        """
        SHA-256 від title+body.

        Статичний метод — можна викликати без інстансу репозиторію.
        IngestSourceUseCase використовує цей метод перед exists_by_hash().
        """
        return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()