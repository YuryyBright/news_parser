# infrastructure/persistence/mappers/source_mapper.py
"""
SourceMapper — єдине місце де живе логіка ORM ↔ Domain.

Mapper знає і про domain (Source), і про ORM (SourceModel).
Ніхто інший не повинен знати про деталі маппінгу:
  - domain НЕ знає про ORM
  - application НЕ знає про ORM
  - тільки infrastructure/persistence містить цей код
"""
from __future__ import annotations

from uuid import UUID

from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import SourceConfig, SourceType
from src.infrastructure.persistence.models import SourceModel


class SourceMapper:
    """Static mapper — без стану, просто перетворення."""

    @staticmethod
    def to_model(source: Source) -> SourceModel:
        """Domain entity → ORM model (для збереження в БД)."""
        return SourceModel(
            id=str(source.id),
            name=source.name,
            url=source.config.url,
            source_type=source.config.source_type.value,
            fetch_interval_sec=source.config.fetch_interval_seconds,
            config={},               # розширення для майбутніх полів
            is_active=source.is_active,
        )

    @staticmethod
    def to_domain(model: SourceModel) -> Source:
        """ORM model → Domain entity (після читання з БД)."""
        return Source(
            id=UUID(model.id),
            name=model.name,
            config=SourceConfig(
                url=model.url,
                source_type=SourceType(model.source_type),
                fetch_interval_seconds=model.fetch_interval_sec,
            ),
            is_active=model.is_active,
            created_at=model.created_at,
        )
