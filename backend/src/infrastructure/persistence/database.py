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
from sqlalchemy import text
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
    
    # Додаємо timeout і сюди, про всяк випадок, щоб DDL операції не падали одразу
    engine = create_async_engine(
        settings.database.url, 
        echo=False,
        connect_args={"timeout": 20}
    )
    
    try:
        from src.infrastructure.persistence.models import Base
        async with engine.begin() as conn:
            # Увімкнення WAL режиму для кращої конкурентності (корисно для SQLite)
            if "sqlite" in settings.database.url:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA synchronous=NORMAL;"))
                
            await conn.run_sync(Base.metadata.create_all)
    finally:
        # Гарантуємо закриття пулу з'єднань
        await engine.dispose()


async def get_session_for_scripts(
    database_url: str,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Допоміжна функція для CLI-скриптів та Alembic env.py.
    НЕ використовувати в application code — там є Container.db_session().
    """
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"timeout": 20}  # Чекати до 20 секунд зняття блокування
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with factory() as session:
            # Віддаємо чисту сесію. Скрипт сам має викликати session.commit()
            yield session
    finally:
        # Безпечне закриття з'єднань незалежно від того, як відпрацював скрипт
        await engine.dispose()