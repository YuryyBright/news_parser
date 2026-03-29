# infrastructure/vector_store/article_vector_repo.py
"""
ArticleVectorRepository — реалізує IArticleEmbeddingRepository.

Залежності:
  ✅ domain.knowledge.repositories.IArticleEmbeddingRepository (порт)
  ✅ domain.knowledge.entities.ArticleEmbedding (domain entity)
  ✅ chromadb (зовнішня бібліотека)

Розмір вектора: беремо ТІЛЬКИ з settings.embedding.dimensions.
Якщо модель зміниться — достатньо оновити settings.
"""
from __future__ import annotations

import logging
from uuid import UUID

import chromadb
import numpy as np

from domain.knowledge.entities import ArticleEmbedding
from domain.knowledge.repositories import IArticleEmbeddingRepository

logger = logging.getLogger(__name__)


class ArticleVectorRepository(IArticleEmbeddingRepository):
    """
    Реалізує IArticleEmbeddingRepository через ChromaDB.

    Колекція: одна колекція для всіх embedding статей.
    HNSW metric: cosine similarity (повертає distances 0..2, конвертуємо в 0..1).
    """

    def __init__(self, client: chromadb.AsyncClientAPI) -> None:
        self._client = client
        # Lazy import — settings ще можуть не бути готові при __init__
        from config.settings import get_settings
        cfg = get_settings()
        self._col_name = cfg.chroma.collection_articles
        self._dim = cfg.embedding.dimensions

    async def _get_collection(self):
        """get_or_create колекції з правильними параметрами."""
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension": self._dim,
            },
        )

    # ─── IRepository (base) ───────────────────────────────────────────────────

    async def get(self, id: UUID) -> ArticleEmbedding | None:
        return await self.get_by_article_id(id)

    async def save(self, embedding: ArticleEmbedding) -> None:
        await self.upsert(embedding)

    async def update(self, embedding: ArticleEmbedding) -> None:
        await self.upsert(embedding)

    async def delete(self, id: UUID) -> None:
        col = await self._get_collection()
        await col.delete(ids=[str(id)])
        logger.debug("Embedding deleted: article_id=%s", id)

    async def list(self) -> list[ArticleEmbedding]:
        # Не підтримується для vector store — занадто великий результат
        raise NotImplementedError("list() not supported for vector store")

    # ─── IArticleEmbeddingRepository ──────────────────────────────────────────

    async def get_by_article_id(self, article_id: UUID) -> ArticleEmbedding | None:
        col = await self._get_collection()
        result = await col.get(
            ids=[str(article_id)],
            include=["embeddings", "metadatas"],
        )
        if not result["embeddings"]:
            return None

        vector = np.array(result["embeddings"][0], dtype=np.float32)
        meta = result["metadatas"][0] if result["metadatas"] else {}

        return ArticleEmbedding(
            id=article_id,
            article_id=article_id,
            vector=vector,
            model_version=meta.get("model_version", "unknown"),
            dimensions=len(vector),
        )

    # ─── Специфічні методи ────────────────────────────────────────────────────

    async def upsert(self, embedding: ArticleEmbedding) -> None:
        """Зберігає або оновлює embedding статті."""
        if len(embedding.vector) != self._dim:
            raise ValueError(
                f"Vector dim mismatch: expected {self._dim}, got {len(embedding.vector)}"
            )
        col = await self._get_collection()
        await col.upsert(
            ids=[str(embedding.article_id)],
            embeddings=[embedding.vector.tolist()],
            metadatas=[{"model_version": embedding.model_version}],
        )
        logger.debug("Embedding upserted: article_id=%s", embedding.article_id)

    async def query_similar(
        self,
        query_vector: np.ndarray,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Пошук схожих статей за cosine similarity.

        Returns:
            [(article_id, similarity_score), ...] — відсортовано за score DESC.
            score ∈ [0.0, 1.0], де 1.0 = ідентичний вектор.
        """
        if len(query_vector) != self._dim:
            raise ValueError(
                f"Query vector dim mismatch: expected {self._dim}, got {len(query_vector)}"
            )

        col = await self._get_collection()
        kwargs: dict = {
            "query_embeddings": [query_vector.tolist()],
            "n_results": n_results,
            "include": ["distances"],
        }
        if where:
            kwargs["where"] = where

        results = await col.query(**kwargs)

        ids = results["ids"][0]
        distances = results["distances"][0]

        # Chroma cosine distance ∈ [0, 2]:
        #   0 = identical, 2 = opposite
        # Конвертуємо в similarity ∈ [0, 1]
        return [
            (UUID(id_), max(0.0, 1.0 - dist / 2.0))
            for id_, dist in zip(ids, distances)
        ]

    async def get_vector(self, article_id: UUID) -> np.ndarray | None:
        """Повертає тільки вектор без метаданих (швидше)."""
        col = await self._get_collection()
        result = await col.get(
            ids=[str(article_id)],
            include=["embeddings"],
        )
        if not result["embeddings"]:
            return None
        return np.array(result["embeddings"][0], dtype=np.float32)