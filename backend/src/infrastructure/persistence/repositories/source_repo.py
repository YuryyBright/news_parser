# infrastructure/persistence/repositories/source_repo.py
"""
Реалізація ISourceRepository через SQLAlchemy.

Infrastructure знає про domain-інтерфейс (ISourceRepository),
але application НЕ знає про SQLAlchemy — лише про порт.
"""
from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Імпорт ТІЛЬКИ з infrastructure та application.ports
from application.ports import ISourceRepository, SourceDTO
from infrastructure.persistence.models import SourceModel


class SourceRepository(ISourceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_active(self) -> list[SourceDTO]:
        result = await self._session.execute(
            select(SourceModel).where(SourceModel.is_active == True)
        )
        return [_to_dto(m) for m in result.scalars().all()]

    async def get_by_id(self, source_id: UUID) -> SourceDTO | None:
        result = await self._session.execute(
            select(SourceModel).where(SourceModel.id == str(source_id))
        )
        model = result.scalar_one_or_none()
        return _to_dto(model) if model else None

    async def save(self, source: SourceDTO) -> None:
        existing = await self._session.get(SourceModel, str(source.id))
        if existing:
            existing.name = source.name
            existing.url = source.url
            existing.is_active = source.is_active
        else:
            self._session.add(SourceModel(
                id=str(source.id),
                name=source.name,
                url=source.url,
                source_type=source.source_type,
                config=source.config,
                fetch_interval_sec=source.fetch_interval_sec,
                is_active=source.is_active,
            ))
        await self._session.flush()


def _to_dto(model: SourceModel) -> SourceDTO:
    """Конвертує ORM-модель у DTO — не витікає деталей БД назовні."""
    return SourceDTO(
        id=UUID(model.id),
        name=model.name,
        url=model.url,
        source_type=model.source_type,
        config=model.config or {},
        fetch_interval_sec=model.fetch_interval_sec,
        is_active=model.is_active,
    )