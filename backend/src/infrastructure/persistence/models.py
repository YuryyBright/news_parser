# infrastructure/persistence/models.py
"""
SQLAlchemy ORM моделі.

Правило імпортів:
  ✅ from config.settings import get_settings   ← правильно
Моделі не знають про domain entities — це задача mapper'ів.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean, Float, ForeignKey, Integer, String, Text,
    TIMESTAMP, UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


from src.config.settings import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Lazy settings — викликаємо get_settings() тільки там де потрібне значення ──
# Не зберігаємо settings на рівні модуля: якщо .env ще не завантажений при
# імпорті models.py — буде помилка. Lambda відкладає виклик до першого INSERT.

def _default_fetch_interval() -> int:
    return get_settings().celery.fetch_interval_seconds


def _default_threshold() -> float:
    return get_settings().filtering.default_threshold


def _default_weights() -> dict:
    w = get_settings().filtering.weights
    return {"embedding": w.embedding, "keyword": w.keyword, "feedback": w.feedback}


# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════

class UserModel(Base):
    __tablename__ = "users"

    id:              Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email:           Mapped[str]      = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    name:            Mapped[str]      = mapped_column(String(255), nullable=False)
    is_active:       Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at:      Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    updated_at:      Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, onupdate=utcnow)

    profile:        Mapped["UserProfileModel"]             = relationship(back_populates="user", uselist=False)
    feed_snapshots: Mapped[list["FeedSnapshotModel"]]      = relationship(back_populates="user")
    read_history:   Mapped[list["ReadHistoryModel"]]       = relationship(back_populates="user")
    feedback:       Mapped[list["RelevanceFeedbackModel"]] = relationship(back_populates="user")


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION
# ══════════════════════════════════════════════════════════════════════════════

class SourceModel(Base):
    __tablename__ = "sources"

    id:                 Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name:               Mapped[str]      = mapped_column(String(255), nullable=False)
    url:                Mapped[str]      = mapped_column(Text, nullable=False, unique=True)
    source_type:        Mapped[str]      = mapped_column(String(50), nullable=False)
    config:             Mapped[dict]     = mapped_column(JSON, default=dict)
    fetch_interval_sec: Mapped[int]      = mapped_column(Integer, default=_default_fetch_interval)
    is_active:          Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at:         Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)

    fetch_jobs:   Mapped[list["FetchJobModel"]]   = relationship(back_populates="source")
    raw_articles: Mapped[list["RawArticleModel"]] = relationship(back_populates="source")
    articles:     Mapped[list["ArticleModel"]]    = relationship(back_populates="source")


class FetchJobModel(Base):
    __tablename__ = "fetch_jobs"

    id:            Mapped[str]             = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id:     Mapped[str]             = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    status:        Mapped[str]             = mapped_column(String(50), default="pending")
    retries:       Mapped[int]             = mapped_column(Integer, default=0)
    error_message: Mapped[str | None]      = mapped_column(Text)
    last_run_at:   Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at:    Mapped[datetime]        = mapped_column(TIMESTAMP, default=utcnow)

    source: Mapped["SourceModel"] = relationship(back_populates="fetch_jobs")


class RawArticleModel(Base):
    __tablename__ = "raw_articles"
    __table_args__ = (
        UniqueConstraint("url", name="uq_raw_url"),
        Index("ix_raw_hash", "content_hash"),
        Index("ix_raw_status", "status"),
    )

    id:           Mapped[str]             = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id:    Mapped[str | None]      = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    title:        Mapped[str]             = mapped_column(Text, nullable=False)
    body:         Mapped[str]             = mapped_column(Text, nullable=False)
    url:          Mapped[str]             = mapped_column(Text, nullable=False)
    language:     Mapped[str | None]      = mapped_column(String(10))
    content_hash: Mapped[str]             = mapped_column(String(64), nullable=False)
    status:       Mapped[str]             = mapped_column(String(50), default="pending")  # pending | deduplicated | processed
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at:   Mapped[datetime]        = mapped_column(TIMESTAMP, default=utcnow)

    source: Mapped["SourceModel"] = relationship(back_populates="raw_articles")


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE
# ══════════════════════════════════════════════════════════════════════════════

class ArticleModel(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("url", name="uq_article_url"),
        UniqueConstraint("content_hash", name="uq_article_hash"),   # ← dedup за хешем
        Index("ix_article_status", "status"),
        Index("ix_article_score", "relevance_score"),
        Index("ix_article_published", "published_at"),
    )

    id:              Mapped[str]             = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id:       Mapped[str | None]      = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    raw_article_id:  Mapped[str | None]      = mapped_column(ForeignKey("raw_articles.id", ondelete="SET NULL"))
    title:           Mapped[str]             = mapped_column(Text, nullable=False)
    body:            Mapped[str]             = mapped_column(Text, nullable=False)
    url:             Mapped[str]             = mapped_column(Text, nullable=False)
    language:        Mapped[str]             = mapped_column(String(10), default="unknown")
    status:          Mapped[str]             = mapped_column(String(50), default="pending")
    relevance_score: Mapped[float]           = mapped_column(Float, default=0.0)
    content_hash:    Mapped[str]             = mapped_column(String(64), nullable=False)
    published_at:    Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at:      Mapped[datetime]        = mapped_column(TIMESTAMP, default=utcnow)

    source:     Mapped["SourceModel | None"]          = relationship(back_populates="articles")
    tags:       Mapped[list["TagModel"]]              = relationship(secondary="article_tags", back_populates="articles")
    feed_items: Mapped[list["FeedItemModel"]]         = relationship(back_populates="article")
    feedback:   Mapped[list["RelevanceFeedbackModel"]] = relationship(back_populates="article")


class TagModel(Base):
    __tablename__ = "tags"

    id:       Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name:     Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source:   Mapped[str] = mapped_column(String(50), default="auto")

    articles: Mapped[list["ArticleModel"]] = relationship(secondary="article_tags", back_populates="tags")


class ArticleTagModel(Base):
    __tablename__ = "article_tags"

    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    tag_id:     Mapped[str] = mapped_column(ForeignKey("tags.id",     ondelete="CASCADE"), primary_key=True)


# ══════════════════════════════════════════════════════════════════════════════
# USER PROFILE & FILTERING
# ══════════════════════════════════════════════════════════════════════════════

class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id:    Mapped[str]      = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    preference: Mapped[dict]     = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, onupdate=utcnow)

    user:     Mapped["UserModel"]           = relationship(back_populates="profile")
    criteria: Mapped["FilterCriteriaModel"] = relationship(back_populates="user_profile", uselist=False)


class FilterCriteriaModel(Base):
    __tablename__ = "filter_criteria"

    id:                Mapped[str]   = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_profile_id:   Mapped[str]   = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), unique=True)
    phrases:           Mapped[list]  = mapped_column(JSON, default=list)
    keywords:          Mapped[list]  = mapped_column(JSON, default=list)
    allowed_languages: Mapped[list]  = mapped_column(JSON, default=list)
    threshold:         Mapped[float] = mapped_column(Float, default=_default_threshold)
    feedback_prior:    Mapped[float] = mapped_column(Float, default=0.50)
    feedback_count:    Mapped[int]   = mapped_column(Integer, default=0)
    weights:           Mapped[dict]  = mapped_column(JSON, default=_default_weights)
    updated_at:        Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, onupdate=utcnow)

    user_profile: Mapped["UserProfileModel"] = relationship(back_populates="criteria")


class RelevanceFeedbackModel(Base):
    __tablename__ = "relevance_feedback"
    __table_args__ = (UniqueConstraint("user_id", "article_id"),)

    id:                Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id:           Mapped[str]      = mapped_column(ForeignKey("users.id",    ondelete="CASCADE"))
    article_id:        Mapped[str]      = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    criteria_id:       Mapped[str | None] = mapped_column(ForeignKey("filter_criteria.id", ondelete="SET NULL"))
    liked:             Mapped[bool]     = mapped_column(Boolean, nullable=False)
    score_at_feedback: Mapped[float]    = mapped_column(Float, default=0.0)
    created_at:        Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)

    user:    Mapped["UserModel"]    = relationship(back_populates="feedback")
    article: Mapped["ArticleModel"] = relationship(back_populates="feedback")


# ══════════════════════════════════════════════════════════════════════════════
# FEED
# ══════════════════════════════════════════════════════════════════════════════

class FeedSnapshotModel(Base):
    __tablename__ = "feed_snapshots"

    id:           Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id:      Mapped[str]      = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    is_stale:     Mapped[bool]     = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)

    user:  Mapped["UserModel"]           = relationship(back_populates="feed_snapshots")
    items: Mapped[list["FeedItemModel"]] = relationship(back_populates="snapshot", lazy="selectin")


class FeedItemModel(Base):
    __tablename__ = "feed_items"

    id:          Mapped[str]   = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str]   = mapped_column(ForeignKey("feed_snapshots.id", ondelete="CASCADE"))
    article_id:  Mapped[str]   = mapped_column(ForeignKey("articles.id",       ondelete="CASCADE"))
    rank:        Mapped[int]   = mapped_column(Integer, default=0)
    score:       Mapped[float] = mapped_column(Float, default=0.0)
    status:      Mapped[str]   = mapped_column(String(50), default="unread")

    snapshot: Mapped["FeedSnapshotModel"] = relationship(back_populates="items")
    article:  Mapped["ArticleModel"]      = relationship(back_populates="feed_items", lazy="selectin")


class ReadHistoryModel(Base):
    __tablename__ = "read_history"
    __table_args__ = (UniqueConstraint("user_id", "article_id"),)

    id:             Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id:        Mapped[str]           = mapped_column(ForeignKey("users.id",    ondelete="CASCADE"), index=True)
    article_id:     Mapped[str]           = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    time_spent_sec: Mapped[int | None]    = mapped_column(Integer)
    read_at:        Mapped[datetime]      = mapped_column(TIMESTAMP, default=utcnow)

    user: Mapped["UserModel"] = relationship(back_populates="read_history")