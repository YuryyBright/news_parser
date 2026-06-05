# src/infrastructure/persistence/repositories/handbook_events_repo.py
"""
Repository for handbook events.
"""
from __future__ import annotations

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.handbook_events import EventModel


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict, created_by: str = "system") -> EventModel:
        m = EventModel(**data, created_by=created_by)
        self.session.add(m)
        await self.session.flush()
        return m

    async def get(self, event_id: str) -> EventModel | None:
        result = await self.session.execute(
            select(EventModel).where(EventModel.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_for_person(self, person_id: str) -> list[EventModel]:
        result = await self.session.execute(
            select(EventModel)
            .where(EventModel.person_id == person_id)
            .order_by(EventModel.date.desc())
        )
        return list(result.scalars().all())

    async def list_for_org_unit(self, org_unit_id: str) -> list[EventModel]:
        result = await self.session.execute(
            select(EventModel)
            .where(EventModel.org_unit_id == org_unit_id)
            .order_by(EventModel.date.desc())
        )
        return list(result.scalars().all())

    async def list_for_country(self, country_id: str) -> list[EventModel]:
        result = await self.session.execute(
            select(EventModel)
            .where(EventModel.country_id == country_id)
            .order_by(EventModel.date.desc())
        )
        return list(result.scalars().all())

    async def list_for_article(self, article_id: str) -> list[EventModel]:
        result = await self.session.execute(
            select(EventModel)
            .where(EventModel.article_id == article_id)
            .order_by(EventModel.date.desc())
        )
        return list(result.scalars().all())

    async def update(self, event_id: str, data: dict) -> EventModel | None:
        m = await self.get(event_id)
        if not m:
            return None
        for k, v in data.items():
            setattr(m, k, v)
        return m

    async def delete(self, event_id: str) -> bool:
        m = await self.get(event_id)
        if not m:
            return False
        await self.session.delete(m)
        return True

