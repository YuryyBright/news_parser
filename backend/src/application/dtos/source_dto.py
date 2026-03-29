# application/dtos/source_dto.py
"""
Data Transfer Objects для Sources.

Це прості незмінні структури для передачі даних між шарами.
DTO ≠ domain entity: DTO не має поведінки, лише дані.

Application визначає ці DTO — presentation і infrastructure їх використовують,
але ніколи не визначають власних "domain" структур.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AddSourceCommand:
    """Вхідні дані для AddSourceUseCase."""
    name: str
    url: str
    source_type: str                 # "rss" | "web" | "api" | "telegram"
    fetch_interval_seconds: int = 300


@dataclass(frozen=True)
class SourceView:
    """
    Вихідні дані use cases що повертають джерело.
    Presentation отримує SourceView і перетворює на HTTP-схему.
    """
    id: UUID
    name: str
    url: str
    source_type: str
    fetch_interval_seconds: int
    is_active: bool
    created_at: datetime
