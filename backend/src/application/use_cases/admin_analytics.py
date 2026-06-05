# application/use_cases/admin_analytics.py
from __future__ import annotations

from datetime import date

from src.application.dtos.admin_dto import (
    AdminOverviewStats, TimeSeriesPoint, LanguageDistribution,
    TagStats, ScoreHistogramBin, SourcePerformance, AdminTimeSeriesQuery,
)
from src.infrastructure.persistence.repositories.admin_analytics_repo import AdminAnalyticsRepository


class GetAdminOverviewUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> AdminOverviewStats:
        return await self.repo.get_overview_stats(from_date=from_date, to_date=to_date, language=language)


class GetTimeSeriesUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(self, query: AdminTimeSeriesQuery) -> list[TimeSeriesPoint]:
        return await self.repo.get_time_series(
            from_date=query.from_date,
            to_date=query.to_date,
            language=query.language,
        )


class GetLanguageDistributionUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[LanguageDistribution]:
        return await self.repo.get_language_distribution(from_date=from_date, to_date=to_date)


class GetTopTagsUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        limit: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[TagStats]:
        return await self.repo.get_top_tags(limit=limit, from_date=from_date, to_date=to_date, language=language)


class GetScoreHistogramUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        bins: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[ScoreHistogramBin]:
        return await self.repo.get_score_histogram(bins=bins, from_date=from_date, to_date=to_date, language=language)


class GetSourcesPerformanceUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[SourcePerformance]:
        return await self.repo.get_sources_performance(from_date=from_date, to_date=to_date, language=language)


class GetPopularArticlesUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        limit: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[dict]:
        return await self.repo.get_popular_articles(limit=limit, from_date=from_date, to_date=to_date, language=language)


class GetUserStatsUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(self) -> dict:
        return await self.repo.get_user_stats()


class GetArticleStatusDistributionUseCase:
    def __init__(self, repo: AdminAnalyticsRepository):
        self.repo = repo

    async def execute(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[dict]:
        return await self.repo.get_article_status_distribution(from_date=from_date, to_date=to_date, language=language)