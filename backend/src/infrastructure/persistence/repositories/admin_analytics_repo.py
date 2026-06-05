# infrastructure/persistence/repositories/admin_analytics_repo.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy import func, select, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models import (
    ArticleModel, SourceModel, UserModel,
    GeneratedNewsModel, FeedSnapshotModel, FeedItemModel,
    TagModel, ArticleTagModel, FetchJobModel, UserFeedbackModel,
)
from src.application.dtos.admin_dto import (
    AdminOverviewStats, TimeSeriesPoint, LanguageDistribution,
    TagStats, ScoreHistogramBin, SourcePerformance,
)


class AdminAnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── helpers ──────────────────────────────────────────────────────────────

    def _apply_article_filters(self, stmt, from_date=None, to_date=None, language=None):
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)
        if language:
            stmt = stmt.where(ArticleModel.language == language)
        return stmt

    # ─── overview ─────────────────────────────────────────────────────────────

    async def get_overview_stats(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> AdminOverviewStats:

        # Статті
        art_stmt = select(
            func.count(ArticleModel.id),
            func.sum(case((ArticleModel.status == "accepted", 1), else_=0)),
            func.sum(case((ArticleModel.status == "rejected", 1), else_=0)),
            func.sum(case((ArticleModel.status == "expired",  1), else_=0)),
            func.sum(case((ArticleModel.status == "pending",  1), else_=0)),
            func.avg(ArticleModel.relevance_score),
        )
        art_stmt = self._apply_article_filters(art_stmt, from_date, to_date, language)
        articles = await self._session.execute(art_stmt)
        total, acc, rej, exp, pend, avg_score = articles.one()
        total = total or 0

        # Джерела
        sources = await self._session.execute(
            select(
                func.count(SourceModel.id),
                func.sum(case((SourceModel.is_active == True, 1), else_=0)),
            )
        )
        total_src, active_src = sources.one()

        # Користувачі
        total_users = await self._session.scalar(select(func.count(UserModel.id)))

        # UserFeedback
        uf_stmt = select(
            func.count(UserFeedbackModel.id),
            func.sum(case((UserFeedbackModel.liked == True,  1), else_=0)),
            func.sum(case((UserFeedbackModel.liked == False, 1), else_=0)),
        )
        if language:
            uf_stmt = (
                uf_stmt
                .join(ArticleModel, UserFeedbackModel.article_id == ArticleModel.id)
                .where(ArticleModel.language == language)
            )
        if from_date:
            uf_stmt = uf_stmt.where(UserFeedbackModel.created_at >= from_date)
        if to_date:
            uf_stmt = uf_stmt.where(UserFeedbackModel.created_at <= to_date)

        uf = await self._session.execute(uf_stmt)
        total_fb, uf_liked, uf_disliked = uf.one()

        # Generated news
        gen_stmt = select(func.count(GeneratedNewsModel.id))
        if from_date:
            gen_stmt = gen_stmt.where(GeneratedNewsModel.created_at >= from_date)
        if to_date:
            gen_stmt = gen_stmt.where(GeneratedNewsModel.created_at <= to_date)
        gen_news = await self._session.scalar(gen_stmt)

        # Нові користувачі сьогодні
        today = datetime.utcnow().date()
        new_today = await self._session.scalar(
            select(func.count(UserModel.id))
            .where(func.date(UserModel.created_at) == today)
        )

        acc_rate = (acc or 0) / total * 100 if total > 0 else 0
        rej_rate = (rej or 0) / total * 100 if total > 0 else 0

        return AdminOverviewStats(
            total_articles=total,
            accepted_articles=acc or 0,
            rejected_articles=rej or 0,
            expired_articles=exp or 0,
            pending_articles=pend or 0,
            total_sources=total_src or 0,
            active_sources=active_src or 0,
            total_users=total_users or 0,
            total_feedback=total_fb or 0,
            liked_feedback=uf_liked or 0,
            disliked_feedback=uf_disliked or 0,
            avg_relevance_score=float(avg_score or 0),
            total_read_actions=0,           # не рахуємо поки
            generated_news_count=gen_news or 0,
            acceptance_rate=acc_rate,
            rejection_rate=rej_rate,
            avg_time_spent_sec=0.0,         # не рахуємо поки
            active_users_today=0,           # не рахуємо поки
            new_users_today=new_today or 0,
            engagement_rate=0.0,            # не рахуємо поки
        )

    # ─── time series ──────────────────────────────────────────────────────────

    async def get_time_series(
        self, from_date: date | None, to_date: date | None, language: str | None
    ) -> list[TimeSeriesPoint]:
        # Статті по днях
        art_stmt = (
            select(
                func.date(ArticleModel.created_at).label("day"),
                func.count(ArticleModel.id).label("created"),
                func.sum(case((ArticleModel.status == "accepted", 1), else_=0)).label("accepted"),
                func.avg(ArticleModel.relevance_score).label("avg_score"),
            )
            .group_by(func.date(ArticleModel.created_at))
        )
        art_stmt = self._apply_article_filters(art_stmt, from_date, to_date, language)
        articles_by_day = await self._session.execute(art_stmt)
        articles_map = {
            row.day: (row.created, row.accepted, row.avg_score or 0)
            for row in articles_by_day
        }

        # UserFeedback по днях
        uf_stmt = (
            select(
                func.date(UserFeedbackModel.created_at).label("day"),
                func.sum(case((UserFeedbackModel.liked == True,  1), else_=0)).label("liked"),
                func.sum(case((UserFeedbackModel.liked == False, 1), else_=0)).label("disliked"),
            )
            .group_by(func.date(UserFeedbackModel.created_at))
        )
        if from_date:
            uf_stmt = uf_stmt.where(UserFeedbackModel.created_at >= from_date)
        if to_date:
            uf_stmt = uf_stmt.where(UserFeedbackModel.created_at <= to_date)
        if language:
            uf_stmt = (
                uf_stmt
                .join(ArticleModel, UserFeedbackModel.article_id == ArticleModel.id)
                .where(ArticleModel.language == language)
            )
        uf_by_day = await self._session.execute(uf_stmt)
        fb_map = {row.day: (row.liked or 0, row.disliked or 0) for row in uf_by_day}

        all_days = set(articles_map.keys()) | set(fb_map.keys())
        result = []
        for day in sorted(all_days):
            created, accepted, avg_sc = articles_map.get(day, (0, 0, 0))
            liked, disliked = fb_map.get(day, (0, 0))
            result.append(TimeSeriesPoint(
                date=day,
                articles_created=created or 0,
                articles_accepted=accepted or 0,
                feedback_liked=liked,
                feedback_disliked=disliked,
                avg_relevance_score=float(avg_sc),
                read_count=0,           # не рахуємо поки
                active_users=0,         # не рахуємо поки
            ))
        return result

    # ─── language distribution ────────────────────────────────────────────────

    async def get_language_distribution(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[LanguageDistribution]:
        stmt = (
            select(
                ArticleModel.language,
                func.count(ArticleModel.id).label("count"),
            )
            .group_by(ArticleModel.language)
            .order_by(func.count(ArticleModel.id).desc())
        )
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)

        rows = await self._session.execute(stmt)
        items = rows.all()
        total = sum(r.count for r in items)
        return [
            LanguageDistribution(
                language=r.language,
                count=r.count,
                percentage=(r.count / total * 100) if total > 0 else 0,
            )
            for r in items
        ]

    # ─── top tags ─────────────────────────────────────────────────────────────

    async def get_top_tags(
        self,
        limit: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[TagStats]:
        stmt = (
            select(
                TagModel.name.label("tag_name"),
                func.count(ArticleModel.id).label("total"),
                func.sum(case((ArticleModel.status == "accepted", 1), else_=0)).label("accepted"),
                func.avg(ArticleModel.relevance_score).label("avg_score"),
            )
            .join(ArticleTagModel, TagModel.id == ArticleTagModel.tag_id)
            .join(ArticleModel,    ArticleTagModel.article_id == ArticleModel.id)
            .group_by(TagModel.name)
            .order_by(func.count(ArticleModel.id).desc())
            .limit(limit)
        )
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)
        if language:
            stmt = stmt.where(ArticleModel.language == language)

        rows = await self._session.execute(stmt)
        return [
            TagStats(
                tag_name=name,
                articles_count=total_count,
                accepted_count=accepted_count or 0,
                avg_score=float(avg_score or 0),
            )
            for name, total_count, accepted_count, avg_score in rows.all()
        ]

    # ─── score histogram ──────────────────────────────────────────────────────

    async def get_score_histogram(
        self,
        bins: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[ScoreHistogramBin]:
        base_stmt = select(func.count(ArticleModel.id))
        base_stmt = self._apply_article_filters(base_stmt, from_date, to_date, language)
        total = await self._session.scalar(base_stmt)
        if not total:
            return []

        step = 1.0 / bins
        buckets = []
        for i in range(bins):
            low  = i * step
            high = (i + 1) * step if i < bins - 1 else 1.0
            count_stmt = (
                select(func.count(ArticleModel.id))
                .where(ArticleModel.relevance_score >= low)
                .where(ArticleModel.relevance_score <= high)
            )
            count_stmt = self._apply_article_filters(count_stmt, from_date, to_date, language)
            count = await self._session.scalar(count_stmt)
            pct   = (count or 0) / total * 100 if total > 0 else 0
            buckets.append(ScoreHistogramBin(
                bucket_min=low,
                bucket_max=high,
                count=count or 0,
                percentage=pct,
            ))
        return buckets

    # ─── sources performance ──────────────────────────────────────────────────

    async def get_sources_performance(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[SourcePerformance]:
        stmt = (
            select(
                SourceModel.id,
                SourceModel.name,
                SourceModel.is_active,
                func.count(ArticleModel.id).label("total"),
                func.sum(case((ArticleModel.status == "accepted", 1), else_=0)).label("accepted"),
                func.sum(case((ArticleModel.status == "rejected", 1), else_=0)).label("rejected"),
                func.avg(ArticleModel.relevance_score).label("avg_score"),
                func.max(FetchJobModel.last_run_at).label("last_fetch"),
            )
            .outerjoin(ArticleModel,  SourceModel.id == ArticleModel.source_id)
            .outerjoin(FetchJobModel, SourceModel.id == FetchJobModel.source_id)
            .group_by(SourceModel.id, SourceModel.name, SourceModel.is_active)
            .order_by(func.count(ArticleModel.id).desc())
        )
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)
        if language:
            stmt = stmt.where(ArticleModel.language == language)

        rows = await self._session.execute(stmt)
        result = []
        for row in rows.all():
            total    = row.total    or 0
            rejected = row.rejected or 0
            result.append(SourcePerformance(
                source_id=row.id,
                source_name=row.name,
                total_articles=total,
                accepted_articles=row.accepted or 0,
                avg_score=float(row.avg_score or 0),
                is_active=row.is_active,
                rejection_rate=(rejected / total * 100) if total > 0 else 0,
                articles_per_day=total / 30,
                last_fetch_at=row.last_fetch,
            ))
        return result

    # ─── popular articles ─────────────────────────────────────────────────────

    async def get_popular_articles(
        self,
        limit: int = 10,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                ArticleModel.id,
                ArticleModel.title,
                SourceModel.name.label("source_name"),
                ArticleModel.language,
                ArticleModel.relevance_score,
                ArticleModel.published_at,
                func.sum(case((UserFeedbackModel.liked == True,  1), else_=0)).label("liked"),
                func.sum(case((UserFeedbackModel.liked == False, 1), else_=0)).label("disliked"),
            )
            .outerjoin(UserFeedbackModel, ArticleModel.id == UserFeedbackModel.article_id)
            .outerjoin(SourceModel,       ArticleModel.source_id == SourceModel.id)
            .where(ArticleModel.status == "accepted")
            .group_by(
                ArticleModel.id, ArticleModel.title, SourceModel.name,
                ArticleModel.language, ArticleModel.relevance_score, ArticleModel.published_at,
            )
            .order_by(
                (
                    func.sum(case((UserFeedbackModel.liked == True, 1), else_=0)) -
                    func.sum(case((UserFeedbackModel.liked == False, 1), else_=0))
                ).desc()
            )
            .limit(limit)
        )
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)
        if language:
            stmt = stmt.where(ArticleModel.language == language)

        rows = await self._session.execute(stmt)
        return [
            {
                "article_id":       row.id,
                "title":            row.title,
                "source_name":      row.source_name,
                "language":         row.language,
                "relevance_score":  float(row.relevance_score),
                "published_at":     row.published_at,
                "read_count":       0,                  # не рахуємо поки
                "liked":            row.liked    or 0,
                "disliked":         row.disliked or 0,
                "engagement_score": (row.liked or 0) / max((row.liked or 0) + (row.disliked or 0), 1) * 100,
            }
            for row in rows.all()
        ]

    # ─── user stats ───────────────────────────────────────────────────────────

    async def get_user_stats(self) -> dict:
        total_users = await self._session.scalar(select(func.count(UserModel.id)))

        today    = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)

        new_today = await self._session.scalar(
            select(func.count(UserModel.id))
            .where(func.date(UserModel.created_at) == today)
        )
        new_week = await self._session.scalar(
            select(func.count(UserModel.id))
            .where(func.date(UserModel.created_at) >= week_ago)
        )

        # Активні за фідбеком (замість ReadHistory)
        active_today = await self._session.scalar(
            select(func.count(distinct(UserFeedbackModel.user_id)))
            .where(func.date(UserFeedbackModel.created_at) == today)
        )
        active_week = await self._session.scalar(
            select(func.count(distinct(UserFeedbackModel.user_id)))
            .where(func.date(UserFeedbackModel.created_at) >= week_ago)
        )

        feedback_per_user_sq = (
            select(func.count(UserFeedbackModel.id).label("cnt"))
            .group_by(UserFeedbackModel.user_id)
            .subquery()
        )
        avg_feedback = await self._session.scalar(
            select(func.avg(feedback_per_user_sq.c.cnt))
        ) or 0

        returning_rate = (
            ((active_week or 0) - (new_week or 0)) / max((active_week or 1), 1) * 100
        )

        return {
            "total_users":            total_users  or 0,
            "active_today":           active_today or 0,
            "active_week":            active_week  or 0,
            "new_today":              new_today    or 0,
            "new_week":               new_week     or 0,
            "returning_rate":         returning_rate,
            "avg_articles_per_user":  0.0,           # не рахуємо поки
            "avg_feedback_per_user":  float(avg_feedback),
        }
    async def get_article_status_distribution(self, from_date: date | None = None, to_date: date | None = None, language: str | None = None) -> list[dict]:
        """Розподіл статей по статусам"""
        total = await self._session.scalar(
            select(func.count(ArticleModel.id))
        )
        stmt = (
            select(
                ArticleModel.status,
                func.count(ArticleModel.id).label("count"),
            )
            .group_by(ArticleModel.status)            
            .order_by(func.count(ArticleModel.id).desc())       

        )
        if from_date:
            stmt = stmt.where(ArticleModel.created_at >= from_date)
        if to_date:
            stmt = stmt.where(ArticleModel.created_at <= to_date)
        if language:
            stmt = stmt.where(ArticleModel.language == language)

        rows = await self._session.execute(stmt)
        return [
            {
                "status": r.status,
                "count": r.count,
                "percentage": (r.count / total * 100) if total > 0 else 0,
            }
            for r in rows.all()
        ]