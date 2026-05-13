# infrastructure/dedup/minhash_repo.py
"""
Реалізації IMinHashRepository.

InMemoryMinHashRepository    — для unit тестів (ізольовано, без I/O)
SqlAlchemyMinHashRepository  — для dev і production (таблиця minhash_signatures)

Схема зберігання в БД:
  Таблиця: minhash_signatures
  Колонки: raw_article_id (PK, FK → raw_articles), signature (JSON), num_perm, created_at

Пошук near-duplicate:
  WHERE created_at >= now() - 3 days  →  завантажуємо підписи
  Jaccard O(N) в пам'яті.

  Оцінка: 3 дні × ~500 статей = ~1500 рядків.
  1500 × 128 int × 8 bytes ≈ 1.5MB — цілком прийнятно.
  При зростанні до 10k+ статей/день — замінити на LSH або pgvector.

ВИДАЛЕНО: RedisMinHashRepository (не потрібен — вся персистентність в БД).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.deduplication.repositories import IMinHashRepository
from src.domain.deduplication.services import MinHashSignature

logger = logging.getLogger(__name__)

_DB_WINDOW_DAYS = 3  # порівнюємо тільки зі статтями за останні 3 дні


# ── InMemory (тільки для unit тестів) ─────────────────────────────────────────

class InMemoryMinHashRepository(IMinHashRepository):
    """
    Зберігає підписи в пам'яті процесу.

    Підходить ТІЛЬКИ для:
      - unit тестів (ізольовано, без I/O, без БД)

    НЕ використовувати для:
      - dev-сервера (є SqlAlchemyMinHashRepository)
      - production
    """

    def __init__(self) -> None:
        self._store: dict[UUID, MinHashSignature] = {}

    async def save(self, raw_id: UUID, signature: MinHashSignature) -> None:
        self._store[raw_id] = signature

    async def find_similar(
        self,
        signature: MinHashSignature,
        threshold: float,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        results: list[tuple[UUID, float]] = []

        for stored_id, stored_sig in self._store.items():
            if stored_sig.num_perm != signature.num_perm:
                logger.warning(
                    "MinHash num_perm mismatch: stored=%d query=%d, skipping raw_id=%s",
                    stored_sig.num_perm, signature.num_perm, stored_id,
                )
                continue

            similarity = signature.jaccard(stored_sig)
            if similarity >= threshold:
                results.append((stored_id, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def delete(self, raw_id: UUID) -> None:
        self._store.pop(raw_id, None)
        logger.debug("MinHash deleted (memory): raw_id=%s", raw_id)

    def __len__(self) -> int:
        return len(self._store)


# ── SqlAlchemy (dev + production) ─────────────────────────────────────────────

class SqlAlchemyMinHashRepository(IMinHashRepository):
    """
    Зберігає MinHash підписи в таблиці minhash_signatures.

    Near-duplicate пошук обмежений вікном _DB_WINDOW_DAYS (3 дні):
      - статті старші 3 днів не можуть бути "свіжими дублікатами"
      - WHERE created_at >= cutoff + індекс ix_minhash_created → швидко

    Args:
        session: AsyncSession — той самий що у raw_repo і article_repo,
                 тобто всі зміни в одній транзакції.

    Переваги над Redis:
      - не потрібен окремий сервіс
      - дані не втрачаються при рестарті
      - вікно керується через SQL, а не TTL
      - ON DELETE CASCADE автоматично чистить підписи видалених статей
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, raw_id: UUID, signature: MinHashSignature) -> None:
        from src.infrastructure.persistence.models import MinHashSignatureModel

        model = MinHashSignatureModel(
            raw_article_id=str(raw_id),
            signature=signature.signature,
            num_perm=signature.num_perm,
        )
        self._session.add(model)
        await self._session.flush()
        logger.debug("MinHash saved (db): raw_id=%s", raw_id)

    async def find_similar(
        self,
        signature: MinHashSignature,
        threshold: float,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        """
        Завантажує підписи за останні _DB_WINDOW_DAYS днів, порівнює Jaccard.

        SQL:
          SELECT * FROM minhash_signatures
          WHERE created_at >= :cutoff
          -- індекс ix_minhash_created покриває цей фільтр
        """
        from src.infrastructure.persistence.models import MinHashSignatureModel

        cutoff = datetime.now(timezone.utc) - timedelta(days=_DB_WINDOW_DAYS)

        result = await self._session.execute(
            select(MinHashSignatureModel).where(
                MinHashSignatureModel.created_at >= cutoff
            )
        )
        rows = result.scalars().all()

        matches: list[tuple[UUID, float]] = []
        for row in rows:
            if row.num_perm != signature.num_perm:
                logger.warning(
                    "MinHash num_perm mismatch: stored=%d query=%d, skipping raw_id=%s",
                    row.num_perm, signature.num_perm, row.raw_article_id,
                )
                continue

            stored = MinHashSignature(
                signature=row.signature,
                num_perm=row.num_perm,
            )
            sim = signature.jaccard(stored)
            if sim >= threshold:
                matches.append((UUID(row.raw_article_id), sim))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    async def delete(self, raw_id: UUID) -> None:
        from src.infrastructure.persistence.models import MinHashSignatureModel

        model = await self._session.get(MinHashSignatureModel, str(raw_id))
        if model:
            await self._session.delete(model)
            await self._session.flush()
        logger.debug("MinHash deleted (db): raw_id=%s", raw_id)