# application/use_cases/deactivate_source.py
"""
DeactivateSourceUseCase — soft-deactivate джерела новин.

Бізнес-правила:
  - Джерело має існувати (інакше SourceNotFoundError)
  - Вже деактивоване джерело — idempotent (не кидає помилку)
  - Деактивація не видаляє пов'язані статті / raw_articles

DDD:
  ✅ мутація стану — через aggregate метод source.deactivate()
  ✅ залежить від ISourceRepository (порту), не від ORM
  ✅ повертає None (command, не query)
"""
from __future__ import annotations

import logging
from uuid import UUID

from src.domain.ingestion.repositories import ISourceRepository

logger = logging.getLogger(__name__)


class SourceNotFoundError(Exception):
    """Source не знайдено. Presentation → HTTP 404."""
    def __init__(self, source_id: UUID) -> None:
        super().__init__(f"Source '{source_id}' not found")
        self.source_id = source_id


class DeactivateSourceUseCase:
    """
    Деактивує джерело через aggregate метод.

    Ідемпотентний: якщо джерело вже неактивне — просто повертає None
    без помилки. Логіку "вже деактивовано" вирішує aggregate.
    """

    def __init__(self, source_repo: ISourceRepository) -> None:
        self._sources = source_repo

    async def execute(self, source_id: UUID) -> None:
        source = await self._sources.get(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        # Aggregate сам вирішує чи є що деактивовувати
        source.deactivate()

        await self._sources.update(source)

        logger.info("Source deactivated: id=%s name=%s", source.id, source.name)
