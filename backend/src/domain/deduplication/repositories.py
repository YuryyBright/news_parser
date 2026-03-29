# domain/deduplication/repositories.py
"""
Порти для ingestion домену.

IMinHashRepository — зберігає/шукає MinHash підписи.
IRawArticleRepository — доступ до raw_articles.

Реалізації — в infrastructure (Redis або PostgreSQL для MinHash,
SqlAlchemy для RawArticle).
"""
from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from src.domain.shared.base_repository import IRepository
from .services import MinHashSignature
from src.domain.knowledge.entities import Article
from .value_objects import ContentHash


class IRawArticleRepository(IRepository[Article]):

    @abstractmethod
    async def get_by_url(self, url: str) -> Article | None: ...

    @abstractmethod
    async def get_by_hash(self, content_hash: ContentHash) -> Article | None: ...

    @abstractmethod
    async def mark_as_deduplicated(self, raw_id: UUID, duplicate_of: UUID) -> None:
        """Позначити raw article як дублікат і вказати оригінал."""
        ...

    @abstractmethod
    async def mark_as_processed(self, raw_id: UUID) -> None:
        """Позначити raw article як успішно оброблений (пройшов dedup → article створено)."""
        ...

    @abstractmethod
    async def mark_as_invalid(self, raw_id: UUID, reason: str) -> None:
        """Позначити raw article як невалідний."""
        ...

    @abstractmethod
    async def list_pending(self, limit: int = 100) -> list[Article]:
        """Отримати необроблені raw articles для pipeline."""
        ...


class IMinHashRepository:
    """
    Порт для збереження і пошуку MinHash підписів.

    Зберігає: {raw_article_id → MinHashSignature}
    Шукає: closest neighbors за Jaccard similarity.

    Реалізації:
      - RedisMinHashRepository  (hash в Redis, LSH buckets для пошуку)
      - PostgresMinHashRepository (масив в pgvector або JSON колонка)
      - InMemoryMinHashRepository (для тестів)
    """

    @abstractmethod
    async def save(self, raw_id: UUID, signature: MinHashSignature) -> None: ...

    @abstractmethod
    async def find_similar(
        self,
        signature: MinHashSignature,
        threshold: float,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        """
        Знайти схожі підписи.

        Returns:
            [(raw_article_id, similarity_score), ...] відсортовано DESC
        """
        ...

    @abstractmethod
    async def delete(self, raw_id: UUID) -> None: ...
