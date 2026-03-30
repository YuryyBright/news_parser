# infrastructure/persistence/mappers/article_mapper.py
"""
Маппери ORM ↔ Domain для ingestion та knowledge контекстів.

ArticleMapper    — Article (knowledge domain)
RawArticleMapper — RawArticle (ingestion domain)
FetchJobMapper   — FetchJob (ingestion domain)

Всі три живуть тут бо всі три пов'язані з однією групою ORM моделей.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

from src.domain.knowledge.entities import Article, Tag
from src.domain.knowledge.value_objects import (
    ArticleStatus, ContentHash, Language, PublishedAt,
)
from src.domain.ingestion.entities import FetchJob, FetchJobStatus, RawArticle
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.persistence.models import (
    ArticleModel, FetchJobModel, RawArticleModel, TagModel,
)


# ── Article (knowledge) ───────────────────────────────────────────────────────

class ArticleMapper:

    @staticmethod
    def to_model(article: Article, raw_article_id: str | None = None) -> ArticleModel:
        """
        Domain Article → ORM ArticleModel.

        raw_article_id: передається явно з use case якщо відома
        (трасування: яка RawArticle породила цю Article).
        """
        return ArticleModel(
            id=str(article.id),
            source_id=str(article.source_id) if article.source_id else None,
            raw_article_id=raw_article_id,                      # ← було відсутнє
            title=article.title,
            body=article.body,
            url=article.url,
            language=article.language.value,
            status=article.status.value,
            relevance_score=article.relevance_score,
            content_hash=article.content_hash.value if article.content_hash else "",
            published_at=article.published_at.value if article.published_at else None,
        )

    @staticmethod
    def to_domain(model: ArticleModel) -> Article:
        """ORM ArticleModel → Domain Article."""
        tags = [
            Tag(id=UUID(t.id), name=t.name, source=t.source)
            for t in (model.tags or [])
        ]
        return Article(
            id=UUID(model.id),
            source_id=UUID(model.source_id) if model.source_id else None,
            title=model.title,
            body=model.body,
            url=model.url,
            language=_safe_language(model.language),
            status=ArticleStatus(model.status),
            relevance_score=model.relevance_score,
            content_hash=ContentHash(value=model.content_hash) if model.content_hash else None,
            published_at=PublishedAt(value=model.published_at) if model.published_at else None,
            tags=tags,
            created_at=model.created_at,
        )


# ── RawArticle (ingestion) ────────────────────────────────────────────────────

class RawArticleMapper:

    @staticmethod
    def to_model(raw: RawArticle) -> RawArticleModel:
        """
        Domain RawArticle → ORM RawArticleModel.

        content_hash береться з raw.content_hash якщо вже порахований use case'ом,
        інакше рахується тут (fallback щоб маппер завжди був коректним).
        """
        content_hash = raw.content_hash or _compute_hash(
            raw.content.title, raw.content.body
        )
        return RawArticleModel(
            id=str(raw.id),
            source_id=str(raw.source_id) if raw.source_id else None,
            title=raw.content.title,
            body=raw.content.body,
            url=raw.content.url,
            language=raw.content.language,
            content_hash=content_hash,
            published_at=raw.content.published_at,
        )

    @staticmethod
    def to_domain(model: RawArticleModel) -> RawArticle:
        """ORM RawArticleModel → Domain RawArticle."""
        return RawArticle(
            id=UUID(model.id),
            source_id=UUID(model.source_id) if model.source_id else None,
            content=ParsedContent(
                title=model.title,
                body=model.body,
                url=model.url,
                published_at=model.published_at,
                language=model.language,
            ),
            content_hash=model.content_hash,
            created_at=model.created_at,
        )


# ── FetchJob (ingestion) ──────────────────────────────────────────────────────

class FetchJobMapper:

    @staticmethod
    def to_model(job: FetchJob) -> FetchJobModel:
        """Domain FetchJob → ORM FetchJobModel."""
        return FetchJobModel(
            id=str(job.id),
            source_id=str(job.source_id),
            status=job.status.value,
            retries=job.retries,
            error_message=job.error_message,
            last_run_at=job.last_run_at,
        )

    @staticmethod
    def to_domain(model: FetchJobModel) -> FetchJob:
        """ORM FetchJobModel → Domain FetchJob."""
        return FetchJob(
            id=UUID(model.id),
            source_id=UUID(model.source_id),
            status=FetchJobStatus(model.status),
            retries=model.retries,
            error_message=model.error_message,
            last_run_at=model.last_run_at,
            created_at=model.created_at,
        )


# ── Утиліти ───────────────────────────────────────────────────────────────────

def _safe_language(value: str | None) -> Language:
    try:
        return Language(value) if value else Language.UNKNOWN
    except ValueError:
        return Language.UNKNOWN


def _compute_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()