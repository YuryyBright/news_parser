# application/dtos/admin_dto.py (РОЗШИРЕНА ВЕРСІЯ)
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class AdminOverviewStats:
    """Основні метрики системи"""
    total_articles: int
    accepted_articles: int
    rejected_articles: int
    expired_articles: int
    pending_articles: int
    total_sources: int
    active_sources: int
    total_users: int
    total_feedback: int
    liked_feedback: int
    disliked_feedback: int
    avg_relevance_score: float
    total_read_actions: int
    generated_news_count: int
    
    # НОВІ ПОЛЯ для розширених метрик
    acceptance_rate: float = 0.0  # %
    rejection_rate: float = 0.0   # %
    avg_time_spent_sec: float = 0.0  # середній час читання
    active_users_today: int = 0
    new_users_today: int = 0
    engagement_rate: float = 0.0  # feedback / read_actions * 100


@dataclass
class TimeSeriesPoint:
    """Точка часового ряду"""
    date: date
    articles_created: int
    articles_accepted: int
    feedback_liked: int
    feedback_disliked: int
    read_count: int
    active_users: int
    # НОВІ
    users_active: int = 0
    read_actions: int = 0
    avg_score_that_day: float = 0.0
    avg_relevance_score: float = 0.0

@dataclass
class LanguageDistribution:
    """Розподіл по мовах"""
    language: str
    count: int
    percentage: float


@dataclass
class TagStats:
    """Статистика тегів"""
    tag_name: str
    articles_count: int
    # НОВІ
    accepted_count: int = 0
    avg_score: float = 0.0


@dataclass
class ScoreHistogramBin:
    """Бін гістограми оцінок"""
    bucket_min: float
    bucket_max: float
    count: int
    # НОВІ
    percentage: float = 0.0


@dataclass
class SourcePerformance:
    """Продуктивність джерела"""
    source_id: str
    source_name: str
    total_articles: int
    accepted_articles: int
    avg_score: float
    is_active: bool
    # НОВІ
    rejection_rate: float = 0.0
    articles_per_day: float = 0.0
    last_fetch_at: datetime | None = None


@dataclass
class ArticlePopularity:
    """Популярна стаття"""
    article_id: str
    title: str
    source_name: str
    language: str
    read_count: int
    liked_count: int
    disliked_count: int
    relevance_score: float
    published_at: datetime
    engagement_score: float = 0.0  # розраховується


@dataclass
class UserStats:
    """Статистика користувачів"""
    total_users: int
    active_users_today: int
    active_users_week: int
    new_users_today: int
    new_users_week: int
    returning_users_rate: float  # %
    avg_articles_per_user: float
    avg_feedback_per_user: float


@dataclass
class ArticleStatusDistribution:
    """Розподіл статей по статусам"""
    status: str  # accepted, rejected, pending, expired
    count: int
    percentage: float


@dataclass
class FeedbackTrend:
    """Тренд фідбеку"""
    date: date
    liked_count: int
    disliked_count: int
    satisfaction_rate: float  # liked / (liked + disliked) * 100


@dataclass
class AdminTimeSeriesQuery:
    """Query для часового ряду"""
    from_date: date | None = None
    to_date: date | None = None
    language: str | None = None