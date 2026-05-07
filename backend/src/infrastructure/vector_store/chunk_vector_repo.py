# infrastructure/vector_store/chunk_vector_repo.py
"""
ChunkVectorRepository — реалізує IChunkVectorRepository для .docx чанків.

Використовує НАЯВНИЙ ChromaDB клієнт (chroma_client.py) і AsyncClientWrapper.
Окрема колекція "docx_chunks" — не перетинається з "articles" (article_vector_repo.py).

Схема в ChromaDB:
  id       = chunk_id  (напр. "file.docx::0042")
  vector   = embedding (dim з settings.embedding.dimensions)
  metadata = {source, language, chunk_index, char_length, ingested_at}

Cosine distance → similarity: sim = 1 - dist / 2  (ChromaDB HNSW cosine)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import numpy as np

from src.application.ports.rag_ports import ChunkRecord, IChunkVectorRepository
from src.domain.news_generation.entities import SearchResult

logger = logging.getLogger(__name__)


class ChunkVectorRepository(IChunkVectorRepository):
    """
    Зберігає та шукає векторні представлення чанків з .docx файлів.

    Args:
        client:       AsyncClientWrapper (або AsyncHttpClient) з chroma_client.py
        collection:   назва колекції (default "docx_chunks")
        dimensions:   розмір вектора — має збігатись з моделлю embedding
    """

    def __init__(
        self,
        client,
        collection_name: str = "docx_chunks",
        dimensions: int = 1024,
    ) -> None:
        self._client     = client
        self._col_name   = collection_name
        self._dim        = dimensions

    async def _get_collection(self):
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension":  self._dim,
            },
        )

    # ── IChunkVectorRepository ────────────────────────────────────────────────

    async def upsert_batch(self, records: list[ChunkRecord]) -> None:
        """
        Зберігає або оновлює список чанків.
        Ідемпотентний: повторний upsert для того ж chunk_id перезаписує.
        """
        if not records:
            return

        # Валідація розмірності
        for r in records:
            if len(r.embedding) != self._dim:
                raise ValueError(
                    f"Embedding dim mismatch for chunk {r.chunk_id}: "
                    f"expected {self._dim}, got {len(r.embedding)}"
                )

        col = await self._get_collection()

        now_iso = datetime.now(timezone.utc).isoformat()

        ids        = [r.chunk_id for r in records]
        embeddings = [r.embedding.tolist() for r in records]
        metadatas  = [
            {
                "source":      r.source,
                "language":    r.language or "unknown",
                "chunk_index": r.metadata.get("chunk_index", 0),
                "char_length": r.metadata.get("char_length", len(r.text)),
                "ingested_at": now_iso,
                **{
                    k: v for k, v in r.metadata.items()
                    if k not in ("chunk_index", "char_length")
                    and isinstance(v, (str, int, float, bool))
                },
            }
            for r in records
        ]
        documents = [r.text for r in records]

        await col.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        logger.debug("[chunk_repo] Upserted %d chunks into '%s'", len(records), self._col_name)

    async def query_similar(
        self,
        query_vector: np.ndarray,
        n_results: int = 10,
        language_filter: str | None = None,
    ) -> list[SearchResult]:
        """
        Семантичний пошук за cosine similarity.

        Args:
            language_filter: якщо передано — фільтрує по metadata.language.
                             Значення "unknown" і "" не фільтруються
                             (щоб не втрачати чанки без детектованої мови).

        Returns:
            list[SearchResult] відсортований DESC за similarity_score.
        """
        if len(query_vector) != self._dim:
            raise ValueError(
                f"Query vector dim mismatch: expected {self._dim}, got {len(query_vector)}"
            )

        col = await self._get_collection()

        kwargs: dict = {
            "query_embeddings": [query_vector.tolist()],
            "n_results":        n_results,
            "include":          ["documents", "metadatas", "distances"],
        }

        if language_filter:
            kwargs["where"] = {"language": {"$in": [language_filter, "unknown", ""]}}

        try:
            results = await col.query(**kwargs)
        except Exception as exc:
            # ChromaDB кидає помилку якщо колекція порожня — обробляємо gracefully
            logger.warning("[chunk_repo] Query failed (empty collection?): %s", exc)
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        output: list[SearchResult] = []
        for chunk_id, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance ∈ [0, 2] → similarity ∈ [0, 1]
            similarity = max(0.0, 1.0 - dist / 2.0)
            output.append(SearchResult(
                chunk_id=chunk_id,
                text=doc or "",
                similarity_score=similarity,
                source=meta.get("source", ""),
                language=meta.get("language", "unknown"),
                metadata=meta,
            ))

        return sorted(output, key=lambda x: x.similarity_score, reverse=True)

    async def count(self) -> int:
        """Повертає загальну кількість чанків у колекції."""
        col = await self._get_collection()
        try:
            result = await col.get(include=[])
            return len(result["ids"])
        except Exception:
            return 0