# infrastructure/vector_store/criteria_vector_repo.py
"""
CriteriaVectorRepository — embedding фраз критеріїв фільтрації.

Не реалізує domain interface (критерії — application-level концепція).
Використовується тільки з FilteringService в application layer.
"""
from __future__ import annotations

import logging
from uuid import UUID

import chromadb
import numpy as np

logger = logging.getLogger(__name__)


class CriteriaVectorRepository:
    """
    Зберігає embedding фраз критеріїв фільтрації.

    Схема зберігання:
      id = "{criteria_id}::{phrase_index}"
      metadata = {criteria_id, phrase, model_version}
    """

    def __init__(self, client: chromadb.AsyncClientAPI) -> None:
        self._client = client
        # Lazy import щоб уникнути проблем з порядком ініціалізації
        from config.settings import get_settings
        cfg = get_settings()
        self._col_name = cfg.chroma.collection_criteria
        self._dim = cfg.embedding.dimensions

    async def _get_collection(self):
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension": self._dim,
            },
        )

    async def upsert_phrases(
        self,
        criteria_id: UUID,
        phrases: list[str],
        embeddings: np.ndarray,   # shape: (N, dim)
        model_version: str,
    ) -> None:
        """
        Зберігає embedding фраз для конкретного criteria.
        Перезаписує попередні embedding для того ж criteria_id.

        Args:
            phrases:    список фраз, відповідає рядкам embeddings
            embeddings: матриця (N × dim) dtype=float32
        """
        if embeddings.ndim != 2:
            raise ValueError(f"Expected 2D embeddings array, got shape {embeddings.shape}")
        if embeddings.shape[1] != self._dim:
            raise ValueError(
                f"Expected {self._dim}d embeddings, got {embeddings.shape[1]}d"
            )
        if len(phrases) != len(embeddings):
            raise ValueError(
                f"phrases ({len(phrases)}) and embeddings ({len(embeddings)}) length mismatch"
            )

        # Спочатку видаляємо старі — щоб не накопичувати при зміні фраз
        await self.delete_for_criteria(criteria_id)

        col = await self._get_collection()
        ids = [f"{criteria_id}::{i}" for i in range(len(phrases))]
        metadatas = [
            {
                "criteria_id": str(criteria_id),
                "phrase": phrase,
                "phrase_index": i,
                "model_version": model_version,
            }
            for i, phrase in enumerate(phrases)
        ]

        await col.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )
        logger.debug(
            "Criteria phrases upserted: criteria_id=%s count=%d",
            criteria_id, len(phrases),
        )

    async def load_for_criteria(
        self, criteria_id: UUID
    ) -> tuple[list[str], np.ndarray] | None:
        """
        Повертає (phrases, embeddings_matrix) або None при cold start.

        Returns:
            None якщо embedding ще не збережені (нові фрази).
            (phrases, matrix) де matrix.shape = (N, dim), dtype=float32.
        """
        col = await self._get_collection()
        result = await col.get(
            where={"criteria_id": str(criteria_id)},
            include=["embeddings", "metadatas"],
        )
        if not result["ids"]:
            return None

        # Сортуємо за phrase_index щоб відновити правильний порядок
        items = sorted(
            zip(result["metadatas"], result["embeddings"]),
            key=lambda x: x[0].get("phrase_index", 0),
        )
        phrases = [meta["phrase"] for meta, _ in items]
        embeddings = np.array([emb for _, emb in items], dtype=np.float32)

        return phrases, embeddings

    async def query_against_criteria(
        self,
        criteria_id: UUID,
        article_vector: np.ndarray,
        n_results: int = 5,
    ) -> list[tuple[str, float]]:
        """
        Знаходить фрази criteria найближчі до вектора статті.

        Returns:
            [(phrase, similarity_score), ...] відсортовано DESC.
        """
        col = await self._get_collection()
        result = await col.query(
            query_embeddings=[article_vector.tolist()],
            n_results=n_results,
            where={"criteria_id": str(criteria_id)},
            include=["distances", "metadatas"],
        )
        if not result["ids"] or not result["ids"][0]:
            return []

        pairs = []
        for meta, dist in zip(result["metadatas"][0], result["distances"][0]):
            similarity = max(0.0, 1.0 - dist / 2.0)
            pairs.append((meta["phrase"], similarity))

        return sorted(pairs, key=lambda x: x[1], reverse=True)

    async def delete_for_criteria(self, criteria_id: UUID) -> None:
        """Видалити всі embedding для criteria (при оновленні фраз)."""
        col = await self._get_collection()
        await col.delete(where={"criteria_id": str(criteria_id)})
        logger.debug("Criteria embeddings deleted: criteria_id=%s", criteria_id)