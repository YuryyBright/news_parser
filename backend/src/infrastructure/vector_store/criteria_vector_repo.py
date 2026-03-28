# infrastructure/vector_store/criteria_vector_repo.py
from __future__ import annotations
from uuid import UUID
import numpy as np
import chromadb

from src.config.container import get_settings
settings = get_settings()


class CriteriaVectorRepository:
    """Зберігає embedding фраз критеріїв фільтрації."""

    def __init__(self, client: chromadb.AsyncClientAPI) -> None:
        self._client = client
        self._col_name = settings.chroma.collection_criteria
        self._dim =  settings.embedding.dimensions

    async def _col(self):
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={"hnsw:space": "cosine", "dimension": self._dim},
        )

    async def upsert_phrases(
        self,
        criteria_id: UUID,
        phrases: list[str],
        embeddings: np.ndarray,       # shape: (N, dim)
        model_version: str,
    ) -> None:
        if embeddings.shape[1] != self._dim:
            raise ValueError(
                f"Expected {self._dim}d embeddings, got {embeddings.shape[1]}d"
            )
        col = await self._col()
        ids  = [f"{criteria_id}::{i}" for i in range(len(phrases))]
        meta = [
            {"criteria_id": str(criteria_id), "phrase": p, "model_version": model_version}
            for p in phrases
        ]
        await col.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=meta,
        )

    async def load_for_criteria(
        self, criteria_id: UUID
    ) -> tuple[list[str], np.ndarray] | None:
        """Повертає (phrases, embeddings_matrix) або None якщо cold start."""
        col = await self._col()
        result = await col.get(
            where={"criteria_id": str(criteria_id)},
            include=["embeddings", "metadatas"],
        )
        if not result["ids"]:
            return None
        phrases    = [m["phrase"] for m in result["metadatas"]]
        embeddings = np.array(result["embeddings"], dtype=np.float32)
        return phrases, embeddings

    async def delete_for_criteria(self, criteria_id: UUID) -> None:
        col = await self._col()
        await col.delete(where={"criteria_id": str(criteria_id)})