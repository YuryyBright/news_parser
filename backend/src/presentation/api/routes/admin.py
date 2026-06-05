# presentation/api/routes/admin.py
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Query

from src.config.container import Container, get_container
from src.application.dtos.admin_dto import AdminTimeSeriesQuery
from src.application.use_cases.admin_analytics import (
    GetAdminOverviewUseCase,
    GetTimeSeriesUseCase,
    GetLanguageDistributionUseCase,
    GetTopTagsUseCase,
    GetScoreHistogramUseCase,
    GetSourcesPerformanceUseCase,
    GetPopularArticlesUseCase,
    GetUserStatsUseCase,
    GetArticleStatusDistributionUseCase,
)

router = APIRouter()

# Спільні Query-параметри фільтрації
def common_filters(
    from_date: date | None = Query(None, description="Від дати (включно)"),
    to_date: date | None = Query(None, description="До дати (включно)"),
    language: str | None = Query(None, description="Мова: ro / sk / hu"),
):
    return {"from_date": from_date, "to_date": to_date, "language": language}


@router.get("/overview")
async def admin_overview(
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Основні метрики системи з підтримкою фільтрів."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetAdminOverviewUseCase(repo)
        stats = await uc.execute(**filters)
    return stats


@router.get("/timeseries")
async def admin_timeseries(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    language: str | None = Query(None),
    container: Container = Depends(get_container),
):
    """Часовий ряд метрик."""
    query = AdminTimeSeriesQuery(from_date=from_date, to_date=to_date, language=language)
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetTimeSeriesUseCase(repo)
        points = await uc.execute(query)
    return points


@router.get("/language-distribution")
async def admin_language_distribution(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    container: Container = Depends(get_container),
):
    """Розподіл статей по мовах (фільтр за датами)."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetLanguageDistributionUseCase(repo)
        data = await uc.execute(from_date=from_date, to_date=to_date)
    return data


@router.get("/top-tags")
async def admin_top_tags(
    limit: int = Query(10, ge=1, le=50),
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Топ теги з розширеною статистикою."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetTopTagsUseCase(repo)
        data = await uc.execute(limit=limit, **filters)
    return data


@router.get("/score-histogram")
async def admin_score_histogram(
    bins: int = Query(10, ge=5, le=50),
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Гістограма relevance score."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetScoreHistogramUseCase(repo)
        data = await uc.execute(bins=bins, **filters)
    return data


@router.get("/sources-performance")
async def admin_sources_performance(
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Продуктивність джерел."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetSourcesPerformanceUseCase(repo)
        data = await uc.execute(**filters)
    return data


@router.get("/popular-articles")
async def admin_popular_articles(
    limit: int = Query(10, ge=1, le=50),
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Топ популярні статті за читаннями та фідбеком."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetPopularArticlesUseCase(repo)
        data = await uc.execute(limit=limit, **filters)
    return data


@router.get("/user-stats")
async def admin_user_stats(container: Container = Depends(get_container)):
    """Детальна статистика користувачів (глобальна)."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetUserStatsUseCase(repo)
        data = await uc.execute()
    return data


@router.get("/article-status-distribution")
async def admin_article_status_distribution(
    filters: dict = Depends(common_filters),
    container: Container = Depends(get_container),
):
    """Розподіл статей по статусам."""
    async with container.db_session() as session:
        repo = container.admin_analytics_repo(session)
        uc = GetArticleStatusDistributionUseCase(repo)
        data = await uc.execute(**filters)
    return data