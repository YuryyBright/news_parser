# src/infrastructure/persistence/models/handbook_events.py
"""
Handbook Events — фіксація заходів для персон, структур, країн.
Підключити до handbook.py:
    from src.infrastructure.persistence.models.handbook_events import EventModel
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime,
    ForeignKey, JSON, Index,
)
from sqlalchemy.orm import relationship
from src.infrastructure.persistence.models import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class EventModel(Base):
    """
    Захід — зустріч, переговори, виступ, призначення, тощо.
    Може бути прив'язаний до персони, структури або країни.
    """
    __tablename__ = "hb_events"

    id = Column(String, primary_key=True, default=gen_id)

    # Хто/де відбувся захід
    person_id = Column(String, ForeignKey("hb_persons.id", ondelete="SET NULL"), nullable=True)
    org_unit_id = Column(String, ForeignKey("hb_org_units.id", ondelete="SET NULL"), nullable=True)
    country_id = Column(String, ForeignKey("hb_countries.id", ondelete="SET NULL"), nullable=True)

    # Основні поля
    title = Column(String(500), nullable=False)
    event_type = Column(String(50), nullable=False, default="meeting")
    # Типи: meeting | speech | negotiation | press | travel | appointment | dismissal | signing | sanction | other

    date = Column(DateTime, nullable=False)
    location = Column(String(400))
    description = Column(Text)
    participants = Column(JSON, default=list)  # list[str] — імена учасників
    source_url = Column(String(1000))

    # Прив'язка до новин
    article_id = Column(String, nullable=True)          # soft ref до articles.id
    generated_news_id = Column(String, nullable=True)   # soft ref до generated_news.id

    # Мета
    created_by = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hb_events_person", "person_id"),
        Index("ix_hb_events_org_unit", "org_unit_id"),
        Index("ix_hb_events_country", "country_id"),
        Index("ix_hb_events_date", "date"),
        Index("ix_hb_events_article", "article_id"),
    )