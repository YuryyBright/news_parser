# application/use_cases/add_source.py
"""
AddSourceUseCase — Application Service.

Правила:
  ✓ Імпортує ТІЛЬКИ з domain та власних dtos
  ✗ НЕ імпортує з infrastructure (SQLAlchemy, Redis, Celery...)
  ✗ НЕ імпортує з presentation (FastAPI, Pydantic...)

Use case — це тонкий оркестратор:
  1. Валідує бізнес-правила (не HTTP-правила!)
  2. Будує доменні сутності
  3. Делегує збереження через інтерфейс
  4. Повертає DTO (не доменну сутність)
"""
from __future__ import annotations

import logging
from uuid import UUID

from src.application.dtos.source_dto import AddSourceCommand, SourceView
from src.domain.ingestion.entities import Source
from src.domain.ingestion.repositories import ISourceRepository
from src.domain.ingestion.value_objects import SourceConfig, SourceType

logger = logging.getLogger(__name__)


class SourceAlreadyExistsError(Exception):
    """
    Application-рівень помилка.
    Presentation перетворить її на HTTP 409.
    """
    def __init__(self, url: str) -> None:
        super().__init__(f"Source with URL '{url}' already exists")
        self.url = url


class AddSourceUseCase:
    """
    Додає нове джерело новин.

    Бізнес-інваріанти:
      - URL джерела має бути унікальним
      - fetch_interval >= 60s (перевіряє SourceConfig у domain layer)
      - source_type має бути валідним значенням SourceType enum
    """

    def __init__(self, source_repo: ISourceRepository) -> None:
        self._sources = source_repo

    async def execute(self, cmd: AddSourceCommand) -> SourceView:
        # 1. Бізнес-правило: URL унікальний
        existing = await self._sources.get_by_url(cmd.url)
        if existing is not None:
            raise SourceAlreadyExistsError(cmd.url)

        # 2. Побудова доменної сутності через value objects.
        #    SourceConfig._validate() кине ValueError якщо interval < 60.
        #    SourceType(cmd.source_type) кине ValueError для невідомого типу.
        source = Source(
            name=cmd.name,
            config=SourceConfig(
                url=cmd.url,
                source_type=SourceType(cmd.source_type),
                fetch_interval_seconds=cmd.fetch_interval_seconds,
            ),
        )

        # 3. Зберегти через репозиторій-інтерфейс
        await self._sources.save(source)

        logger.info("Source added: id=%s url=%s", source.id, cmd.url)

        # 4. Повернути SourceView (не доменну сутність — presentation не повинна
        #    знати про доменні методи)
        return _to_view(source)


def _to_view(source: Source) -> SourceView:
    return SourceView(
        id=source.id,
        name=source.name,
        url=source.config.url,
        source_type=source.config.source_type.value,
        fetch_interval_seconds=source.config.fetch_interval_seconds,
        is_active=source.is_active,
        created_at=source.created_at,
    )
