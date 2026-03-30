# infrastructure/persistence/repositories/fetch_job_repo.py
"""
SqlAlchemyFetchJobRepository — реалізує IFetchJobRepository.

FetchJob — журнал запусків fetcher'а для кожного джерела.
Дозволяє IngestSourceUseCase відстежувати стан і retry-логіку.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.entities import FetchJob
from src.domain.ingestion.repositories import IFetchJobRepository
from src.infrastructure.persistence.mappers.article_mapper import FetchJobMapper
from src.infrastructure.persistence.models import FetchJobModel

logger = logging.getLogger(__name__)


class SqlAlchemyFetchJobRepository(IFetchJobRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── IRepository (base) ───────────────────────────────────────────────────

    async def get(self, id: UUID) -> FetchJob | None:
        model = await self._session.get(FetchJobModel, str(id))
        return FetchJobMapper.to_domain(model) if model else None

    async def save(self, job: FetchJob) -> None:
        """Upsert за ID."""
        existing = await self._session.get(FetchJobModel, str(job.id))
        if existing:
            existing.status        = job.status.value
            existing.retries       = job.retries
            existing.error_message = job.error_message
            existing.last_run_at   = job.last_run_at
        else:
            self._session.add(FetchJobMapper.to_model(job))
        await self._session.flush()

    async def update(self, job: FetchJob) -> None:
        await self.save(job)

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(FetchJobModel, str(id))
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def list(self) -> list[FetchJob]:
        result = await self._session.execute(select(FetchJobModel))
        return [FetchJobMapper.to_domain(m) for m in result.scalars().all()]

    # ─── IFetchJobRepository (specific) ──────────────────────────────────────

    async def get_pending(self, limit: int = 10) -> list[FetchJob]:
        """
        Повертає FetchJob зі статусом 'pending'.
        IngestSourceUseCase шукає тут job для свого джерела перед запуском.
        """
        result = await self._session.execute(
            select(FetchJobModel)
            .where(FetchJobModel.status == "pending")
            .order_by(FetchJobModel.created_at.asc())
            .limit(limit)
        )
        return [FetchJobMapper.to_domain(m) for m in result.scalars().all()]

    async def get_by_source_id(self, source_id: UUID) -> FetchJob | None:
        """
        Знайти job для конкретного джерела.
        Зручніше ніж get_pending() коли знаємо source_id.
        """
        result = await self._session.execute(
            select(FetchJobModel)
            .where(FetchJobModel.source_id == str(source_id))
            .order_by(FetchJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return FetchJobMapper.to_domain(model) if model else None