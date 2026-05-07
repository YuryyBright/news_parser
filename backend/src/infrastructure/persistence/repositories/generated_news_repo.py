# infrastructure/persistence/repositories/generated_news_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.news_generation.entities import GeneratedNews
from src.infrastructure.persistence.models import GeneratedNewsModel


class SqlAlchemyGeneratedNewsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, news: GeneratedNews) -> str:
        model = GeneratedNewsModel(
            id=str(news.id),
            title=news.title,
            body=news.body,
            query=news.query,
            status=news.status.value,
            language=getattr(news, "language", "uk"),
            context_score=news.context_score,
            model_used=getattr(news, "model_used", None),
            source_chunks=news.source_chunks,
        )
        self._session.add(model)
        await self._session.flush()
        return str(news.id)

    async def get(self, id: str) -> GeneratedNewsModel | None:
        return await self._session.get(GeneratedNewsModel, id)

    async def list(self, limit: int = 50, offset: int = 0) -> list[GeneratedNewsModel]:
        result = await self._session.execute(
            select(GeneratedNewsModel)
            .order_by(GeneratedNewsModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()