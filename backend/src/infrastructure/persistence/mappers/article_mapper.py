# infrastructure/persistence/mappers/article_mapper.py
"""
ArticleMapper — ORM ↔ Domain для Article та RawArticle.

Правило: тільки infrastructure знає про цей файл.
Domain не знає про ORM. Application не знає про ORM.
"""
from __future__ import annotations

from uuid import UUID

from src.domain.knowledge.entities import Article, ArticleEmbedding, Tag
from src.domain.knowledge.value_objects import (
    ArticleStatus, ContentHash, Language, PublishedAt,
)
from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.persistence.models import ArticleModel, RawArticleModel, TagModel


class ArticleMapper:

    @staticmethod
    def to_model(article: Article) -> ArticleModel:
        """Domain Article → ORM ArticleModel."""
        return ArticleModel(
            id=str(article.id),
            source_id=str(article.source_id) if article.source_id else None,
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
            content_hash = ContentHash(value=model.content_hash) if model.content_hash else None,
            published_at=PublishedAt(value=model.published_at) if model.published_at else None,
            tags=tags,
            created_at=model.created_at,
        )


class RawArticleMapper:

    @staticmethod
    def to_model(raw: RawArticle) -> RawArticleModel:
        return RawArticleModel(
            id=str(raw.id),
            source_id=str(raw.source_id) if raw.source_id else None,
            title=raw.content.title,
            body=raw.content.body,
            url=raw.content.url,
            language=raw.content.language,
            content_hash=_compute_hash(raw.content.title, raw.content.body),
            published_at=raw.content.published_at,
        )

    @staticmethod
    def to_domain(model: RawArticleModel) -> RawArticle:
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
            created_at=model.created_at,
        )


def _safe_language(value: str | None) -> Language:
    try:
        return Language(value) if value else Language.UNKNOWN
    except ValueError:
        return Language.UNKNOWN


def _compute_hash(title: str, body: str) -> str:
    import hashlib
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()