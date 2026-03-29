# presentation/api/schemas/source.py
"""
HTTP-схеми для Sources.

Живуть ТІЛЬКИ в presentation — це HTTP-контракт API.
Pydantic schemas ≠ domain entities ≠ application DTOs.

Presentation mapper: SourceView (application) → SourceResponse (HTTP).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator


class SourceCreateRequest(BaseModel):
    """Тіло запиту POST /api/v1/sources."""
    name: str
    url: HttpUrl
    source_type: str = "rss"
    fetch_interval_seconds: int = 300

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"rss", "web", "api", "telegram"}
        if v not in allowed:
            raise ValueError(f"source_type must be one of {allowed}")
        return v

    @field_validator("fetch_interval_seconds")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        # HTTP-рівень валідація — domain додатково перевірить те саме правило
        if v < 60:
            raise ValueError("fetch_interval_seconds must be >= 60")
        return v


class SourceResponse(BaseModel):
    """Тіло відповіді для GET /sources та POST /sources."""
    id: UUID
    name: str
    url: str
    source_type: str
    fetch_interval_seconds: int
    is_active: bool
    created_at: datetime
