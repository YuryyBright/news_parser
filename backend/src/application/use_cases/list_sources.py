# application/use_cases/list_sources.py
"""
ListSourcesUseCase — read-only query.

У CQRS-стилі це Query, а не Command.
Не модифікує стан — транзакція на запис не потрібна.
"""
from __future__ import annotations

from src.application.dtos.source_dto import SourceView
from src.domain.ingestion.entities import Source
from src.domain.ingestion.repositories import ISourceRepository


class ListSourcesUseCase:
    """Повертає перелік джерел новин."""

    def __init__(self, source_repo: ISourceRepository) -> None:
        self._sources = source_repo

    async def execute(self, active_only: bool = True) -> list[SourceView]:
        if active_only:
            sources = await self._sources.list_active()
        else:
            sources = await self._sources.list()

        return [_to_view(s) for s in sources]


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
