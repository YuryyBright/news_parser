# infrastructure/persistence/database.py
"""
Утиліта для створення таблиць при старті (dev) або перевірки (prod).

ВАЖЛИВО: Engine та SessionFactory живуть в Container, НЕ тут.
Цей модуль містить тільки одну функцію — create_all_tables(),
яка потрібна в lifespan ОДИН раз.

НЕ використовуй get_session() з цього модуля в продакшені —
він призначений тільки для CLI-скриптів та міграцій.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ✅ Правильний імпорт — ТІЛЬКИ з config.settings, не з container
from src.config.settings import get_settings


async def create_all_tables() -> None:
    """
    Створює всі таблиці за метаданими моделей.
    Викликати ТІЛЬКИ при старті застосунку (lifespan).
    В продакшені замінити на Alembic міграції.
    """
    settings = get_settings()
    # Тимчасовий engine тільки для DDL — не зберігаємо як singleton
    engine = create_async_engine(settings.database.url, echo=False)
    try:
        from src.infrastructure.persistence.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def get_session_for_scripts(
    database_url: str,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Допоміжна функція для CLI-скриптів та Alembic env.py.
    НЕ використовувати в application code — там є Container.db_session().
    """
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    await engine.dispose()