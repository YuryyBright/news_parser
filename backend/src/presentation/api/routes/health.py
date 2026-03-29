# presentation/api/routes/health.py
"""
Healthcheck router — мінімальний роутер для перевірки стану сервісу.

Endpoints:
  GET /health — статус сервісу та статистика статей
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.config.container import Container, get_container

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTHCHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Перевірка стану сервісу",
)
async def health(
    container: Container = Depends(get_container),
) -> dict:
    async with container.db_session() as session:
        # Виклик репозиторію або Use Case через контейнер
        counts = await container.article_repo(session).count_by_status()
        
    return {
        "status": "ok",
        "articles": counts,
    }