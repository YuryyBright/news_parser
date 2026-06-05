# infrastructure/persistence/repositories/handbook_repo.py
"""
Repository layer for Handbook domain.
All DB access goes through these classes — no raw SQL in routers.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.persistence.handbook import (
    CountryModel, OrgUnitModel, PersonModel,
    NewsLinkModel, ChangeLogModel,
)
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
# Make sure to import EventModel at the top of your file
from src.infrastructure.persistence.handbook_events import EventModel
from src.infrastructure.persistence.handbook import (
    CountryModel, OrgUnitModel, PersonModel
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _diff(old: dict, new: dict) -> dict:
    """Return only the changed fields."""
    return {
        k: {"old": old.get(k), "new": v}
        for k, v in new.items()
        if v is not None and old.get(k) != v
    }


# ══════════════════════════════════════════════════════════════════════════════
# Country Repository
# ══════════════════════════════════════════════════════════════════════════════

class CountryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict, changed_by: str) -> CountryModel:
        m = CountryModel(**data)
        self._s.add(m)
        await self._s.flush()
        await self._log(m.id, "country", changed_by, "created", diff=data)
        return m

    async def get(self, country_id: str) -> CountryModel | None:
        return await self._s.get(CountryModel, country_id)

    async def get_by_code(self, code: str) -> CountryModel | None:
        r = await self._s.execute(
            select(CountryModel).where(CountryModel.code == code.upper())
        )
        return r.scalar_one_or_none()

    async def get_detail(self, country_id: str) -> CountryModel | None:
        r = await self._s.execute(
            select(CountryModel)
            .where(CountryModel.id == country_id)
            .options(
                selectinload(CountryModel.org_units).options(
                    
                    # ✅ FIX 1: Use .options() to load multiple relationships on 'persons'
                    selectinload(OrgUnitModel.persons).options(
                        selectinload(PersonModel.news_links),
                        selectinload(PersonModel.changelog),
                    ),
                    selectinload(OrgUnitModel.news_links),
                    selectinload(OrgUnitModel.changelog),
                    
                    # ✅ FIX 2: Apply the exact same thorough loading to 'children' 
                    # otherwise the app will crash when rendering nested org units
                    selectinload(OrgUnitModel.children).options(
                        selectinload(OrgUnitModel.persons).options(
                            selectinload(PersonModel.news_links),
                            selectinload(PersonModel.changelog),
                        ),
                        selectinload(OrgUnitModel.news_links),
                        selectinload(OrgUnitModel.changelog),
                    ),
                ),
                selectinload(CountryModel.news_links),
                selectinload(CountryModel.changelog),
            )
        )
        return r.scalar_one_or_none()

    async def list(
        self,
        q: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CountryModel], int]:
        stmt = select(CountryModel)
        if q:
            stmt = stmt.where(
                or_(
                    CountryModel.name_uk.ilike(f"%{q}%"),
                    CountryModel.name_en.ilike(f"%{q}%"),
                    CountryModel.code.ilike(f"%{q}%"),
                )
            )
        if is_active is not None:
            stmt = stmt.where(CountryModel.is_active == is_active)

        total = (await self._s.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()

        rows = (await self._s.execute(
            stmt.order_by(CountryModel.name_uk).limit(limit).offset(offset)
        )).scalars().all()
        return list(rows), total

    async def update(self, country_id: str, data: dict, changed_by: str) -> CountryModel | None:
        m = await self.get(country_id)
        if not m:
            return None
        old = {k: getattr(m, k, None) for k in data}
        for k, v in data.items():
            if v is not None:
                setattr(m, k, v)
        m.updated_at = datetime.utcnow()
        await self._s.flush()
        await self._log(country_id, "country", changed_by, "updated", diff=_diff(old, data))
        return m

    async def delete(self, country_id: str, changed_by: str) -> bool:
        m = await self.get(country_id)
        if not m:
            return False
        await self._log(country_id, "country", changed_by, "deleted")
        await self._s.delete(m)
        await self._s.flush()
        return True

    async def _log(
        self, entity_id: str, entity_type: str,
        changed_by: str, action: str,
        diff: dict | None = None,
    ) -> None:
        entry = ChangeLogModel(
            entity_type=entity_type,
            country_id=entity_id if entity_type == "country" else None,
            changed_by=changed_by,
            action=action,
            diff=diff,
        )
        self._s.add(entry)


# ══════════════════════════════════════════════════════════════════════════════
# OrgUnit Repository
# ══════════════════════════════════════════════════════════════════════════════

class OrgUnitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict, changed_by: str) -> OrgUnitModel:
        # Calculate level
        level = 0
        if data.get("parent_id"):
            parent = await self._s.get(OrgUnitModel, data["parent_id"])
            if parent:
                level = (parent.level or 0) + 1
        data["level"] = level
        m = OrgUnitModel(**data)
        self._s.add(m)
        await self._s.flush()
        self._s.add(ChangeLogModel(
            entity_type="org_unit",
            org_unit_id=m.id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="created",
            diff=data,
        ))
        return m

    async def get(self, unit_id: str):
        stmt = select(OrgUnitModel).where(OrgUnitModel.id == unit_id).options(
            selectinload(OrgUnitModel.children),
            selectinload(OrgUnitModel.persons),
            selectinload(OrgUnitModel.leader),
            selectinload(OrgUnitModel.news_links),
            selectinload(OrgUnitModel.changelog)
        )
        # ✅ Виправлено: self._s замість self.session
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()
    async def get_tree(self, country_id: str) -> list[OrgUnitModel]:
        """Return all units for a country (tree built by service layer)."""
        r = await self._s.execute(
            select(OrgUnitModel)
            .where(OrgUnitModel.country_id == country_id)
            .options(
                # ✅ FIX: Ensure persons load both relationships here too
                selectinload(OrgUnitModel.persons).options(
                    selectinload(PersonModel.news_links),
                    selectinload(PersonModel.changelog),
                ),
                selectinload(OrgUnitModel.news_links),
                selectinload(OrgUnitModel.changelog),
            )
            .order_by(OrgUnitModel.level, OrgUnitModel.sort_order, OrgUnitModel.name)
        )
        return list(r.scalars().all())
    async def get_roots(self, country_id: str) -> list[OrgUnitModel]:
        """Return only top-level units."""
        r = await self._s.execute(
            select(OrgUnitModel)
            .where(
                OrgUnitModel.country_id == country_id,
                OrgUnitModel.parent_id.is_(None),
            )
            .order_by(OrgUnitModel.sort_order, OrgUnitModel.name)
        )
        return list(r.scalars().all())

    async def update(self, unit_id: str, data: dict, changed_by: str) -> OrgUnitModel | None:
        m = await self.get(unit_id)
        if not m:
            return None
        old = {k: getattr(m, k, None) for k in data}
        for k, v in data.items():
            if v is not None:
                setattr(m, k, v)
        m.updated_at = datetime.utcnow()
        await self._s.flush()
        self._s.add(ChangeLogModel(
            entity_type="org_unit",
            org_unit_id=unit_id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="updated",
            diff=_diff(old, data),
        ))
        return m

    async def move(self, unit_id: str, new_parent_id: str | None, changed_by: str) -> OrgUnitModel | None:
        """Move unit to a different parent."""
        m = await self.get(unit_id)
        if not m:
            return None
        old_parent = m.parent_id
        m.parent_id = new_parent_id
        # Recalculate level
        if new_parent_id:
            parent = await self._s.get(OrgUnitModel, new_parent_id)
            m.level = (parent.level or 0) + 1 if parent else 0
        else:
            m.level = 0
        m.updated_at = datetime.utcnow()
        await self._s.flush()
        self._s.add(ChangeLogModel(
            entity_type="org_unit",
            org_unit_id=unit_id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="updated",
            diff={"parent_id": {"old": old_parent, "new": new_parent_id}},
        ))
        return m

    async def delete(self, unit_id: str, changed_by: str) -> bool:
        m = await self.get(unit_id)
        if not m:
            return False
        self._s.add(ChangeLogModel(
            entity_type="org_unit",
            org_unit_id=unit_id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="deleted",
        ))
        await self._s.delete(m)
        await self._s.flush()
        return True


# ══════════════════════════════════════════════════════════════════════════════
# Person Repository
# ══════════════════════════════════════════════════════════════════════════════

class PersonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, person_id: str) -> PersonModel | None:
        # ✅ FIX: Eagerly load the relationships required by the Pydantic response model
        stmt = (
            select(PersonModel)
            .where(PersonModel.id == person_id)
            .options(
                selectinload(PersonModel.news_links),
                selectinload(PersonModel.changelog)
            )
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict, changed_by: str) -> PersonModel:
        m = PersonModel(**data)
        self._s.add(m)
        await self._s.flush()
        
        self._s.add(ChangeLogModel(
            entity_type="person",
            person_id=m.id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="created",
            diff=data,
        ))
        await self._s.flush() # Ensure the changelog is written so the get() catches it
        
        # ✅ FIX: Fetch the newly created record using get() so relationships are loaded
        return await self.get(m.id)

    async def update(self, person_id: str, data: dict, changed_by: str) -> PersonModel | None:
        # Note: If you only need to update, querying without relationships first is slightly faster, 
        # but reusing get() here is perfectly fine unless performance becomes an issue.
        m = await self.get(person_id)
        if not m:
            return None
            
        old = {k: getattr(m, k, None) for k in data}
        for k, v in data.items():
            if v is not None:
                setattr(m, k, v)
        m.updated_at = datetime.utcnow()
        await self._s.flush()
        
        self._s.add(ChangeLogModel(
            entity_type="person",
            person_id=person_id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="updated",
            diff=_diff(old, data),
        ))
        await self._s.flush() # Ensure the changelog is written
        
        # ✅ FIX: Re-fetch or rely on the updated 'm' (since it was fetched via the updated get() method)
        # Because we used the updated `self.get()` at the top, `m` already has the relationships loaded!
        return m

    async def list_by_country(self, country_id: str) -> list[PersonModel]:
        r = await self._s.execute(
            select(PersonModel)
            .where(PersonModel.country_id == country_id)
            .options(selectinload(PersonModel.news_links))
            .order_by(PersonModel.last_name, PersonModel.first_name)
            .options(selectinload(PersonModel.changelog))
        )
        return list(r.scalars().all())

    async def list_by_org_unit(self, org_unit_id: str) -> list[PersonModel]:
        r = await self._s.execute(
            select(PersonModel)
            .where(PersonModel.org_unit_id == org_unit_id)
            .order_by(PersonModel.last_name)
        )
        return list(r.scalars().all())


    async def delete(self, person_id: str, changed_by: str) -> bool:
        m = await self.get(person_id)
        if not m:
            return False
        self._s.add(ChangeLogModel(
            entity_type="person",
            person_id=person_id,
            country_id=m.country_id,
            changed_by=changed_by,
            action="deleted",
        ))
        await self._s.delete(m)
        await self._s.flush()
        return True


# ══════════════════════════════════════════════════════════════════════════════
# NewsLink Repository
# ══════════════════════════════════════════════════════════════════════════════

class NewsLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict) -> NewsLinkModel:
        m = NewsLinkModel(**data)
        self._s.add(m)
        await self._s.flush()
        return m
    async def list_for_generated_news(self, generated_news_id: str) -> list[NewsLinkModel]:
        r = await self._s.execute(
            select(NewsLinkModel)
            .where(NewsLinkModel.generated_news_id == generated_news_id)
            .order_by(NewsLinkModel.created_at.desc())
        )
        return list(r.scalars().all())
    async def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[NewsLinkModel]:
        col_map = {"country": "country_id", "org_unit": "org_unit_id", "person": "person_id"}
        col = col_map.get(entity_type)
        if not col:
            return []
        r = await self._s.execute(
            select(NewsLinkModel)
            .where(getattr(NewsLinkModel, col) == entity_id)
            .order_by(NewsLinkModel.created_at.desc())
        )
        return list(r.scalars().all())

    async def list_for_article(self, article_id: str) -> list[NewsLinkModel]:
        r = await self._s.execute(
            select(NewsLinkModel)
            .where(NewsLinkModel.article_id == article_id)
            .order_by(NewsLinkModel.created_at.desc())
        )
        return list(r.scalars().all())

    async def delete(self, link_id: str) -> bool:
        m = await self._s.get(NewsLinkModel, link_id)
        if not m:
            return False
        await self._s.delete(m)
        await self._s.flush()
        return True


# ══════════════════════════════════════════════════════════════════════════════
# Search Repository
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# Search Repository
# ══════════════════════════════════════════════════════════════════════════════

class HandbookSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def search(self, q: str, limit: int = 20) -> list[dict]:
        results: list[dict] = []
        like = f"%{q}%"
        
        # Balance the search limits across 4 entities now (Countries, OrgUnits, Persons, Events)
        entity_limit = limit // 4 + 1

        # 1. Countries
        r = await self._s.execute(
            select(CountryModel)
            .where(or_(
                CountryModel.name_uk.ilike(like),
                CountryModel.name_en.ilike(like),
                CountryModel.code.ilike(like),
            ))
            .limit(entity_limit)
        )
        for c in r.scalars().all():
            results.append({
                "entity_type": "country",
                "id": c.id,
                "title": c.name_uk,
                "subtitle": c.name_en,
                "country_code": c.code,
                "country_name": c.name_uk,
            })

        # 2. Org units
        r = await self._s.execute(
            select(OrgUnitModel, CountryModel)
            .join(CountryModel, OrgUnitModel.country_id == CountryModel.id)
            .where(or_(
                OrgUnitModel.name.ilike(like),
                OrgUnitModel.short_name.ilike(like),
            ))
            .limit(entity_limit)
        )
        for unit, country in r.all():
            results.append({
                "entity_type": "org_unit",
                "id": unit.id,
                "title": unit.name,
                "subtitle": unit.unit_type,
                "country_code": country.code,
                "country_name": country.name_uk,
            })

        # 3. Persons
        r = await self._s.execute(
            select(PersonModel, CountryModel)
            .join(CountryModel, PersonModel.country_id == CountryModel.id)
            .where(or_(
                PersonModel.first_name.ilike(like),
                PersonModel.last_name.ilike(like),
                PersonModel.position_title.ilike(like),
            ))
            .limit(entity_limit)
        )
        for person, country in r.all():
            full = f"{person.last_name} {person.first_name}".strip()
            results.append({
                "entity_type": "person",
                "id": person.id,
                "title": full,
                "subtitle": person.position_title,
                "country_code": country.code,
                "country_name": country.name_uk,
            })

        # 4. Events
        r = await self._s.execute(
            select(EventModel, CountryModel)
            # Use outerjoin because an event might not have a direct country_id
            .outerjoin(CountryModel, EventModel.country_id == CountryModel.id)
            .where(or_(
                EventModel.title.ilike(like),
                EventModel.description.ilike(like),
                EventModel.location.ilike(like),
            ))
            .limit(entity_limit)
        )
        for event, country in r.all():
            # Format a nice subtitle combining the event type and date
            subtitle = str(event.event_type).capitalize()
            if event.date:
                subtitle += f" ({event.date.strftime('%Y-%m-%d')})"

            results.append({
                "entity_type": "event",
                "id": event.id,
                "title": event.title,
                "subtitle": subtitle,
                "country_code": country.code if country else None,
                "country_name": country.name_uk if country else None,
            })

        # Sort combined results by title length or alphabetically if desired, 
        # or just truncate to the absolute limit.
        return results[:limit]