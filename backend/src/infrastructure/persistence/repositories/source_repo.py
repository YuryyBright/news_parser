# infrastructure/persistence/repositories/source_repo.py
"""
SqlAlchemySourceRepository — реалізує ISourceRepository.

Dependency rule:
  ✓ Знає про domain інтерфейс (ISourceRepository)
  ✓ Знає про ORM (SourceModel, AsyncSession)
  ✓ Знає про mapper (SourceMapper)
  ✗ НЕ знає про use cases
  ✗ НЕ знає про FastAPI/Pydantic
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.entities import Source
from src.domain.ingestion.repositories import ISourceRepository
from src.infrastructure.persistence.mappers.source_mapper import SourceMapper
from src.infrastructure.persistence.models import SourceModel


class SqlAlchemySourceRepository(ISourceRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─── IRepository (базовий інтерфейс) ─────────────────────────────────────

    async def get(self, id: UUID) -> Source | None:
        model = await self._session.get(SourceModel, str(id))
        return SourceMapper.to_domain(model) if model else None

    async def save(self, source: Source) -> None:
        """Upsert: якщо є — оновити поля, якщо ні — вставити."""
        existing = await self._session.get(SourceModel, str(source.id))
        if existing:
            existing.name = source.name
            existing.url = source.config.url
            existing.source_type = source.config.source_type.value
            existing.fetch_interval_sec = source.config.fetch_interval_seconds
            existing.is_active = source.is_active
        else:
            self._session.add(SourceMapper.to_model(source))
        await self._session.flush()

    async def update(self, source: Source) -> None:
        await self.save(source)

    async def delete(self, id: UUID) -> None:
        """Soft-delete: is_active = False."""
        model = await self._session.get(SourceModel, str(id))
        if model:
            model.is_active = False
            await self._session.flush()

    async def list(self) -> list[Source]:
        result = await self._session.execute(select(SourceModel))
        return [SourceMapper.to_domain(m) for m in result.scalars().all()]

    # ─── ISourceRepository (специфічний інтерфейс) ───────────────────────────

    async def list_active(self) -> list[Source]:
        result = await self._session.execute(
            select(SourceModel).where(SourceModel.is_active.is_(True))
        )
        return [SourceMapper.to_domain(m) for m in result.scalars().all()]

    async def get_by_url(self, url: str) -> Source | None:
        """Потрібен AddSourceUseCase для перевірки унікальності."""
        result = await self._session.execute(
            select(SourceModel).where(SourceModel.url == url)
        )
        model = result.scalar_one_or_none()
        return SourceMapper.to_domain(model) if model else None
