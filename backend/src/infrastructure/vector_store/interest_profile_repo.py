# infrastructure/vector_store/interest_profile_repo.py
"""
InterestProfileRepository — зберігає вектори "цікавих" статей.

Концепція:
  Кожна стаття з score >= threshold → її вектор зберігається тут.
  get_centroid() повертає середній вектор = "профіль смаку".
  Новий scoring порівнює нову статтю з цим центроїдом.

Схема в ChromaDB:
  Колекція: "interest_profile" (одна на весь інстанс, без user_id)
  id       = str(article_id)
  vector   = embedding статті (384-dim, multilingual-e5)
  metadata = {score: float, tags: str (comma-separated), added_at: str}

Чому НЕ per-user зараз:
  Поки немає users — один глобальний профіль.
  Коли з'являться users — додати user_id у metadata і WHERE clause.

Centroid strategy:
  Простий середній вектор по всіх збережених статтях.
  Після нормалізації — ефективний proxy для "середньої теми".
  Альтернативи в майбутньому: weighted (нові важливіші), FAISS clustering.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import chromadb
import numpy as np

logger = logging.getLogger(__name__)

# Максимум статей у профілі — щоб колекція не росла нескінченно.
# При досягненні ліміту — видаляємо найстаріші (FIFO).
MAX_PROFILE_SIZE = 500


class InterestProfileRepository:
    """
    Зберігає вектори статей що потрапили в профіль інтересів.

    Args:
        client: AsyncClientAPI з chroma_client.py
    """

    def __init__(self, client: chromadb.AsyncClientAPI) -> None:
        self._client = client
        from src.config.settings import get_settings
        cfg = get_settings()
        # Нова колекція — додай у settings.chroma якщо потрібно
        self._col_name = getattr(cfg.chroma, "collection_interest_profile", "interest_profile")
        self._dim = cfg.embedding.dimensions  # 384

    async def _get_collection(self):
        return await self._client.get_or_create_collection(
            name=self._col_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension": self._dim,
            },
        )

    # ─── Запис ────────────────────────────────────────────────────────────────

    async def add(
        self,
        article_id: UUID,
        vector: np.ndarray,
        score: float,
        tags: list[str],
    ) -> None:
        """
        Зберігає вектор статті у профіль.
        Якщо article_id вже є — оновлює (upsert).
        Якщо розмір перевищує MAX_PROFILE_SIZE — видаляємо найстаріші.
        """
        if len(vector) != self._dim:
            raise ValueError(
                f"Vector dim mismatch: expected {self._dim}, got {len(vector)}"
            )

        col = await self._get_collection()

        # Upsert поточної статті
        await col.upsert(
            ids=[str(article_id)],
            embeddings=[vector.tolist()],
            metadatas=[{
                "score": float(score),
                "tags": ",".join(tags) if tags else "",
                "added_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
        logger.debug("Interest profile: added article_id=%s score=%.3f", article_id, score)

        # Прибираємо зайві якщо перевищили ліміт
        await self._enforce_limit(col)

    async def _enforce_limit(self, col) -> None:
        """Видаляємо найстаріші записи якщо перевищено MAX_PROFILE_SIZE."""
        result = await col.get(include=["metadatas"])
        count = len(result["ids"])
        if count <= MAX_PROFILE_SIZE:
            return

        # Сортуємо за added_at ASC, видаляємо перші (найстаріші)
        items = sorted(
            zip(result["ids"], result["metadatas"]),
            key=lambda x: x[1].get("added_at", ""),
        )
        to_delete = [id_ for id_, _ in items[:count - MAX_PROFILE_SIZE]]
        await col.delete(ids=to_delete)
        logger.info("Interest profile: evicted %d old entries", len(to_delete))

    # ─── Читання ──────────────────────────────────────────────────────────────

    async def get_centroid(self) -> np.ndarray | None:
        """Повертає центроїд (середній вектор) всіх збережених статей."""
        col = await self._get_collection()
        result = await col.get(include=["embeddings"])

        # SAFELY check if embeddings are empty without triggering NumPy's truth value error
        embeddings = result.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            logger.debug("Interest profile: empty (cold start)")
            return None

        matrix = np.array(embeddings, dtype=np.float32)
        centroid = matrix.mean(axis=0)

        # Нормалізуємо
        norm = np.linalg.norm(centroid)
        if norm > 1e-8:
            centroid /= norm

        logger.debug(
            "Interest profile centroid: computed from %d articles", len(embeddings)
        )
        return centroid

    async def remove(self, article_id: UUID) -> bool:
        """
        Видаляє вектор статті з профілю (explicit dislike).

        Returns:
            True  — стаття була у профілі і видалена.
            False — статті не було у профілі (idempotent, не помилка).

        Ефект на центроїд:
            При наступному get_centroid() цей вектор вже не буде врахований.
            Dislike поступово "зсуває" профіль від небажаних тем.
        """
        col = await self._get_collection()
        result = await col.get(ids=[str(article_id)], include=[])
        if not result["ids"]:
            logger.debug(
                "Interest profile: remove skip — article_id=%s not in profile", article_id
            )
            return False

        await col.delete(ids=[str(article_id)])
        logger.info("Interest profile: removed article_id=%s (dislike)", article_id)
        return True

    async def count(self) -> int:
        """Кількість статей у профілі (для моніторингу)."""
        col = await self._get_collection()
        result = await col.get(include=[])
        return len(result["ids"])

    async def contains(self, article_id: UUID) -> bool:
        """Перевірити чи стаття вже є у профілі."""
        col = await self._get_collection()
        result = await col.get(ids=[str(article_id)], include=[])
        return bool(result["ids"])