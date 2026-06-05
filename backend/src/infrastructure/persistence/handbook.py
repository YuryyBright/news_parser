# infrastructure/persistence/models/handbook.py
"""
Handbook domain models — Countries, OrgUnits, Persons, ChangeLog, NewsLinks.
Integrates with existing ArticleModel via news_links table.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON, UniqueConstraint, Index,
)

from sqlalchemy.orm import relationship
from src.infrastructure.persistence.models import Base

def gen_id() -> str:
    return str(uuid.uuid4())


class CountryModel(Base):
    __tablename__ = "hb_countries"

    id = Column(String, primary_key=True, default=gen_id)
    code = Column(String(4), unique=True, nullable=False)          # ISO alpha-2/3, e.g. "UA"
    name_uk = Column(String(200), nullable=False)                  # Назва (укр)
    name_en = Column(String(200), nullable=False)                  # Name (eng)
    flag_emoji = Column(String(8))                                 # 🇺🇦
    capital = Column(String(200))
    description = Column(Text)
    resources = Column(JSON, default=list)                        # [{url, title, type}]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org_units = relationship(
        "OrgUnitModel",
        back_populates="country",
        foreign_keys="OrgUnitModel.country_id",
        cascade="all, delete-orphan",
    )
    news_links = relationship("NewsLinkModel", back_populates="country")
    changelog = relationship("ChangeLogModel", back_populates="country")


class OrgUnitModel(Base):
    """
    Organizational unit — ministry, department, division, etc.
    Self-referencing tree: parent_id → parent OrgUnit.
    Supports versioning: each structural change creates a new snapshot.
    """
    __tablename__ = "hb_org_units"

    id = Column(String, primary_key=True, default=gen_id)
    country_id = Column(String, ForeignKey("hb_countries.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(String, ForeignKey("hb_org_units.id", ondelete="SET NULL"), nullable=True)

    # === НОВІ ПОЛЯ ===
    leader_id = Column(String, ForeignKey("hb_persons.id", ondelete="SET NULL"), nullable=True)
    leader_title = Column(String(200), default="Керівник") # По замовчуванню "Керівник"
    # =================

    name = Column(String(400), nullable=False)
    short_name = Column(String(100))
    unit_type = Column(String(50), default="department")           # ministry|department|division|sector|post
    level = Column(Integer, default=0)                             # depth in tree (cached)
    sort_order = Column(Integer, default=0)
    description = Column(Text)
    legal_basis = Column(Text)                                     # Правова основа
    resources = Column(JSON, default=list)                        # [{url, title}]
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime)                                  # Дата введення в дію
    valid_to = Column(DateTime)                                    # Дата скасування
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    country = relationship("CountryModel", back_populates="org_units", foreign_keys=[country_id])
    parent = relationship("OrgUnitModel", remote_side="OrgUnitModel.id", back_populates="children")
    children = relationship("OrgUnitModel", back_populates="parent", cascade="all, delete-orphan")
    persons = relationship(
        "PersonModel", 
        back_populates="org_unit", 
        foreign_keys="[PersonModel.org_unit_id]"
    )
    leader = relationship(
        "PersonModel", 
        foreign_keys="[OrgUnitModel.leader_id]", 
        post_update=True
    )
    news_links = relationship("NewsLinkModel", back_populates="org_unit")
    changelog = relationship("ChangeLogModel", back_populates="org_unit")

    __table_args__ = (
        Index("ix_hb_org_units_country", "country_id"),
        Index("ix_hb_org_units_parent", "parent_id"),
    )


class PersonModel(Base):
    """
    Person in an org unit — name, position title, photo, dates.
    """
    __tablename__ = "hb_persons"

    id = Column(String, primary_key=True, default=gen_id)
    org_unit_id = Column(String, ForeignKey("hb_org_units.id", ondelete="SET NULL"), nullable=True)
    country_id = Column(String, ForeignKey("hb_countries.id", ondelete="CASCADE"), nullable=False)
    first_name = Column(String(200), nullable=False)
    last_name = Column(String(200), nullable=False)
    patronymic = Column(String(200))
    position_title = Column(String(400))                           # Посада
    rank = Column(String(200))                                     # Звання / ранг
    photo_url = Column(String(500))                                # URL or base64 path
    bio = Column(Text)
    contacts = Column(JSON, default=dict)                         # {email, phone, telegram}
    resources = Column(JSON, default=list)
    date_appointed = Column(DateTime)
    date_dismissed = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org_unit = relationship(
        "OrgUnitModel", 
        back_populates="persons",
        foreign_keys="[PersonModel.org_unit_id]"
    )
    
    news_links = relationship("NewsLinkModel", back_populates="person")
    changelog = relationship("ChangeLogModel", back_populates="person")

    __table_args__ = (
        Index("ix_hb_persons_country", "country_id"),
        Index("ix_hb_persons_org_unit", "org_unit_id"),
    )


class NewsLinkModel(Base):
    """
    Links a generated_news or article to any handbook entity.
    entity_type: 'country' | 'org_unit' | 'person'
    entity_id: the FK of that entity.
    """
    __tablename__ = "hb_news_links"

    id = Column(String, primary_key=True, default=gen_id)
    # Source: either article or generated_news
    article_id = Column(String, nullable=True)                    # FK to articles.id (soft ref)
    generated_news_id = Column(String, nullable=True)             # FK to generated_news.id (soft ref)
    # Target entity
    entity_type = Column(String(20), nullable=False)              # country|org_unit|person
    country_id = Column(String, ForeignKey("hb_countries.id", ondelete="CASCADE"), nullable=True)
    org_unit_id = Column(String, ForeignKey("hb_org_units.id", ondelete="CASCADE"), nullable=True)
    person_id = Column(String, ForeignKey("hb_persons.id", ondelete="CASCADE"), nullable=True)
    # Meta
    note = Column(Text)                                           # Примітка до зв'язку
    pinned_by = Column(String(200))                               # user who pinned
    created_at = Column(DateTime, default=datetime.utcnow)
    excerpt = Column(Text, nullable=True)
    country = relationship("CountryModel", back_populates="news_links")
    org_unit = relationship("OrgUnitModel", back_populates="news_links")
    person = relationship("PersonModel", back_populates="news_links")

    __table_args__ = (
        UniqueConstraint("article_id", "entity_type", "country_id", "org_unit_id", "person_id",
                         name="uq_hb_news_link"),
        Index("ix_hb_news_links_article", "article_id"),
        Index("ix_hb_news_links_gen_news", "generated_news_id"),
    )


class ChangeLogModel(Base):
    """
    Audit trail for every change in handbook entities.
    """
    __tablename__ = "hb_changelog"

    id = Column(String, primary_key=True, default=gen_id)
    entity_type = Column(String(20), nullable=False)              # country|org_unit|person
    country_id = Column(String, ForeignKey("hb_countries.id", ondelete="SET NULL"), nullable=True)
    org_unit_id = Column(String, ForeignKey("hb_org_units.id", ondelete="SET NULL"), nullable=True)
    person_id = Column(String, ForeignKey("hb_persons.id", ondelete="SET NULL"), nullable=True)
    changed_by = Column(String(200), nullable=False)              # username or user_id
    action = Column(String(20), nullable=False)                   # created|updated|deleted
    field_name = Column(String(100))                              # which field changed
    old_value = Column(Text)
    new_value = Column(Text)
    diff = Column(JSON)                                           # full diff dict
    created_at = Column(DateTime, default=datetime.utcnow)

    country = relationship("CountryModel", back_populates="changelog")
    org_unit = relationship("OrgUnitModel", back_populates="changelog")
    person = relationship("PersonModel", back_populates="changelog")

    __table_args__ = (
        Index("ix_hb_changelog_entity", "entity_type", "country_id"),
        Index("ix_hb_changelog_created", "created_at"),
    )