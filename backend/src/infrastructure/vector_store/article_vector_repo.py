# infrastructure/vector_store/article_vector_repo.py
from __future__ import annotations
from uuid import UUID
import numpy as np
import chromadb

from src.config.container import get_settings
settings = get_settings()


from domain.knowledge.entities import ArticleEmbedding


class ArticleVectorRepository:
    """
    Зберігає / шукає embedding статей у Chroma.
    Розмір вектора береться ТІЛЬКИ з settings.embedding.dimensions
    """

    def __init__(self, client: chromadb.AsyncClientAPI) -> None:
        self._client = client
        self._col_name = settings.chroma.collection_articles
        self._dim = settings.embedding.dimensions

    async def _col(self):
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={"hnsw:space": "cosine", "dimension": self._dim},
        )

    async def upsert(self, embedding: ArticleEmbedding) -> None:
        if len(embedding.vector) != self._dim:
            raise ValueError(
                f"Vector dim mismatch: expected {self._dim}, got {len(embedding.vector)}"
            )
        col = await self._col()
        await col.upsert(
            ids=[str(embedding.article_id)],
            embeddings=[embedding.vector.tolist()],
            metadatas=[{"model_version": embedding.model_version}],
        )

    async def get(self, article_id: UUID) -> np.ndarray | None:
        col = await self._col()
        result = await col.get(
            ids=[str(article_id)],
            include=["embeddings"],
        )
        if not result["embeddings"]:
            return None
        return np.array(result["embeddings"][0], dtype=np.float32)

    async def query_similar(
        self,
        query_vector: np.ndarray,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[tuple[UUID, float]]:
        """Повертає [(article_id, similarity_score), ...]"""
        col = await self._col()
        results = await col.query(
            query_embeddings=[query_vector.tolist()],
            n_results=n_results,
            where=where,
            include=["distances"],
        )
        ids       = results["ids"][0]
        distances = results["distances"][0]
        # Chroma cosine повертає distance (0=identical), конвертуємо в similarity
        return [(UUID(id_), 1.0 - dist) for id_, dist in zip(ids, distances)]

    async def delete(self, article_id: UUID) -> None:
        col = await self._col()
        await col.delete(ids=[str(article_id)])