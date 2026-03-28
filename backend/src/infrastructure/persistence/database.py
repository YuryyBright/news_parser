# infrastructure/persistence/database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)

from src.config.container import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database.url,
    echo=settings.embedding.model and False,  # False in prod
    connect_args={"check_same_thread": False},
)

AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    from infrastructure.persistence.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)