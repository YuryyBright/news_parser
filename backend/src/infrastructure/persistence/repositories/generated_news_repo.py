# infrastructure/persistence/repositories/generated_news_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.news_generation.entities import GeneratedNews
from src.infrastructure.persistence.models import GeneratedNewsModel

from sqlalchemy import select, func, or_
from datetime import datetime
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
    async def list_filtered(
        self,
        language: str | None = None,
        status: str | None = None,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list, int]:
        stmt = select(GeneratedNewsModel)

        if language:
            stmt = stmt.where(GeneratedNewsModel.language == language)
        if status:
            stmt = stmt.where(GeneratedNewsModel.status == status)
        if q:
            stmt = stmt.where(GeneratedNewsModel.rewritten_text.ilike(f"%{q}%"))
        if date_from:
            stmt = stmt.where(GeneratedNewsModel.created_at >= date_from)
        if date_to:
            stmt = stmt.where(GeneratedNewsModel.created_at <= date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        order = GeneratedNewsModel.created_at.desc() if sort_dir == "desc" else GeneratedNewsModel.created_at.asc()
        stmt = stmt.order_by(order).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_id(self, news_id):
        result = await self._session.execute(
            select(GeneratedNewsModel).where(GeneratedNewsModel.id == news_id)
        )
        return result.scalar_one_or_none()

    async def mark_published(self, news_id):
        from sqlalchemy import update
        await self._session.execute(
            update(GeneratedNewsModel)
            .where(GeneratedNewsModel.id == news_id)
            .values(status="published", published_at=datetime.utcnow())
        )
        return await self.get_by_id(news_id)