# src/handbook/schemas.py
"""
Pydantic v2 schemas for Handbook API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


# ── Resource link ──────────────────────────────────────────────────────────────
class ResourceLink(BaseModel):
    url: str
    title: str
    resource_type: str = "link"  # link | document | regulation | video


# ── ChangeLog ─────────────────────────────────────────────────────────────────
class ChangeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    changed_by: str
    action: str
    field_name: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    diff: dict | None = None
    created_at: datetime


# ── NewsLink ───────────────────────────────────────────────────────────────────
class NewsLinkCreate(BaseModel):
    article_id: str | None = None
    generated_news_id: str | None = None
    entity_type: str                     # country | org_unit | person
    country_id: str | None = None
    org_unit_id: str | None = None
    person_id: str | None = None
    note: str | None = None
    excerpt: str | None = None
    pinned_by: str = "system"


class NewsLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_id: str | None = None
    generated_news_id: str | None = None
    entity_type: str
    country_id: str | None = None
    excerpt: str | None = None
    org_unit_id: str | None = None
    person_id: str | None = None
    note: str | None = None
    pinned_by: str | None = None
    created_at: datetime


# ── Person ────────────────────────────────────────────────────────────────────
class PersonCreate(BaseModel):
    org_unit_id: str | None = None
    country_id: str
    first_name: str
    last_name: str
    patronymic: str | None = None
    position_title: str | None = None
    rank: str | None = None
    photo_url: str | None = None
    bio: str | None = None
    contacts: dict[str, str] = Field(default_factory=dict)
    resources: list[ResourceLink] = Field(default_factory=list)
    date_appointed: datetime | None = None
    date_dismissed: datetime | None = None
    is_active: bool = True


class PersonUpdate(BaseModel):
    org_unit_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None
    position_title: str | None = None
    rank: str | None = None
    photo_url: str | None = None
    bio: str | None = None
    contacts: dict[str, str] | None = None
    resources: list[ResourceLink] | None = None
    date_appointed: datetime | None = None
    date_dismissed: datetime | None = None
    is_active: bool | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_unit_id: str | None = None
    country_id: str
    first_name: str
    last_name: str
    patronymic: str | None = None
    position_title: str | None = None
    rank: str | None = None
    photo_url: str | None = None
    bio: str | None = None
    contacts: dict = Field(default_factory=dict)
    resources: list = Field(default_factory=list)
    date_appointed: datetime | None = None
    date_dismissed: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    news_links: list[NewsLinkOut] = Field(default_factory=list)
    changelog: list[ChangeLogOut] = Field(default_factory=list)

    @property
    def full_name(self) -> str:
        parts = [self.last_name, self.first_name, self.patronymic]
        return " ".join(p for p in parts if p)


# ── OrgUnit ───────────────────────────────────────────────────────────────────
class OrgUnitCreate(BaseModel):
    country_id: str
    parent_id: str | None = None
    name: str
    short_name: str | None = None
    unit_type: str = "department"
    sort_order: int = 0
    description: str | None = None
    legal_basis: str | None = None
    resources: list[ResourceLink] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool = True
    leader_id: str | None = None
    leader_title: str | None = "Керівник"


class OrgUnitUpdate(BaseModel):
    parent_id: str | None = None
    name: str | None = None
    short_name: str | None = None
    unit_type: str | None = None
    sort_order: int | None = None
    description: str | None = None
    legal_basis: str | None = None
    resources: list[ResourceLink] | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool | None = None
    leader_id: str | None = None
    leader_title: str | None = None
    leader_id: str | None
    leader_title: str | None
    leader: PersonOut | None = None


class OrgUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    country_id: str
    parent_id: str | None = None
    name: str
    short_name: str | None = None
    unit_type: str
    level: int
    sort_order: int
    description: str | None = None
    legal_basis: str | None = None
    resources: list = Field(default_factory=list)
    is_active: bool
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Nested
    children: list["OrgUnitOut"] = Field(default_factory=list)
    persons: list[PersonOut] = Field(default_factory=list)
    news_links: list[NewsLinkOut] = Field(default_factory=list)
    changelog: list[ChangeLogOut] = Field(default_factory=list)


# ── Country ───────────────────────────────────────────────────────────────────
class CountryCreate(BaseModel):
    code: str = Field(min_length=2, max_length=4)
    name_uk: str
    name_en: str
    flag_emoji: str | None = None
    capital: str | None = None
    description: str | None = None
    resources: list[ResourceLink] = Field(default_factory=list)


class CountryUpdate(BaseModel):
    name_uk: str | None = None
    name_en: str | None = None
    flag_emoji: str | None = None
    capital: str | None = None
    description: str | None = None
    resources: list[ResourceLink] | None = None
    is_active: bool | None = None


class CountryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name_uk: str
    name_en: str
    flag_emoji: str | None = None
    capital: str | None = None
    description: str | None = None
    resources: list = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Stats
    org_units_count: int = 0
    persons_count: int = 0


class CountryDetail(CountryOut):
    """Full country with tree of org units."""
    org_units: list[OrgUnitOut] = Field(default_factory=list)   # only root units; children nested
    changelog: list[ChangeLogOut] = Field(default_factory=list)
    news_links: list[NewsLinkOut] = Field(default_factory=list)


# ── Search ────────────────────────────────────────────────────────────────────
class SearchResult(BaseModel):
    entity_type: str                 # country | org_unit | person
    id: str
    title: str
    subtitle: str | None = None
    country_code: str | None = None
    country_name: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[SearchResult]


# ── Paginated list ─────────────────────────────────────────────────────────────
class PaginatedCountries(BaseModel):
    items: list[CountryOut]
    total: int
    page: int
    page_size: int
    pages: int