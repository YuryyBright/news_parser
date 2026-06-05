# src/presentation/api/schemas/handbook_event_schemas.py
"""
Pydantic v2 schemas for Handbook Events.
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EventCreate(BaseModel):
    person_id: str | None = None
    org_unit_id: str | None = None
    country_id: str | None = None
    title: str
    event_type: str = "meeting"
    date: datetime
    location: str | None = None
    description: str | None = None
    participants: list[str] = Field(default_factory=list)
    source_url: str | None = None
    article_id: str | None = None
    generated_news_id: str | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    event_type: str | None = None
    date: datetime | None = None
    location: str | None = None
    description: str | None = None
    participants: list[str] | None = None
    source_url: str | None = None
    article_id: str | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str | None = None
    org_unit_id: str | None = None
    country_id: str | None = None
    title: str
    event_type: str
    date: datetime
    location: str | None = None
    description: str | None = None
    participants: list = Field(default_factory=list)
    source_url: str | None = None
    article_id: str | None = None
    generated_news_id: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Updated NewsLinkCreate with excerpt field ──────────────────────────────────

class NewsLinkCreateV2(BaseModel):
    """
    Розширена схема прив'язки новини — тепер підтримує excerpt (фрагмент тексту).
    Замінює NewsLinkCreate у handbook_schemas.py
    """
    article_id: str | None = None
    generated_news_id: str | None = None
    entity_type: str                     # country | org_unit | person
    country_id: str | None = None
    org_unit_id: str | None = None
    person_id: str | None = None
    excerpt: str | None = None           # ← виділений фрагмент тексту
    note: str | None = None
    excerpt: str | None = None           # ← виділений фрагмент тексту
    pinned_by: str = "system"