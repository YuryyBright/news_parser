# infrastructure/dedup/minhash_repo.py
"""
Реалізації IMinHashRepository.

InMemoryMinHashRepository  — для dev/тестів (втрачається при рестарті)
RedisMinHashRepository     — для production (персистентне зберігання)

Схема зберігання в Redis:
  Key:   "minhash:{raw_article_id}"
  Value: JSON {"signature": [...], "num_perm": 128}
  TTL:   7 днів (статті старші 7 днів не будуть дублікатами)

Пошук near-duplicate:
  InMemory — O(N) брутфорс по всіх збережених підписах.
  Redis    — теж O(N) через SCAN + GET, але зі стороннього процесу.

  Для production з великою базою (100k+ статей) можна замінити на
  Redis з LSH buckets або PostgreSQL + pgvector. Але для старту
  O(N) цілком прийнятний — MinHash порівняння дуже дешеве (побітове).

  Оцінка: 10k статей × 128 int = ~1.3MB в пам'яті, ~5ms на повний скан.
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from src.domain.deduplication.repositories import IMinHashRepository
from src.domain.deduplication.services import MinHashSignature

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "minhash:"
_REDIS_TTL_SECONDS = 7 * 24 * 3600  # 7 днів


# ── InMemory (dev / тести) ─────────────────────────────────────────────────────

class InMemoryMinHashRepository(IMinHashRepository):
    """
    Зберігає підписи в пам'яті процесу.

    Ідеально для:
      - dev-сервера (швидкий старт, без Redis)
      - unit тестів (ізольовано, без I/O)

    НЕ підходить для:
      - production (втрачається при рестарті)
      - кількох worker-процесів (кожен має свою копію)
    """

    def __init__(self) -> None:
        # {raw_article_id: MinHashSignature}
        self._store: dict[UUID, MinHashSignature] = {}

    async def save(self, raw_id: UUID, signature: MinHashSignature) -> None:
        self._store[raw_id] = signature
        logger.debug("MinHash saved (memory): raw_id=%s", raw_id)

    async def find_similar(
        self,
        signature: MinHashSignature,
        threshold: float,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        """
        Брутфорс O(N) по всіх збережених підписах.
        Повертає список (raw_id, similarity) відсортований DESC.
        """
        results: list[tuple[UUID, float]] = []

        for stored_id, stored_sig in self._store.items():
            if stored_sig.num_perm != signature.num_perm:
                # Підписи несумісні (різні num_perm) — пропускаємо
                logger.warning(
                    "MinHash num_perm mismatch: stored=%d query=%d, skipping raw_id=%s",
                    stored_sig.num_perm, signature.num_perm, stored_id,
                )
                continue

            similarity = signature.jaccard(stored_sig)
            if similarity >= threshold:
                results.append((stored_id, similarity))

        # Сортуємо за similarity DESC, беремо перші limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def delete(self, raw_id: UUID) -> None:
        self._store.pop(raw_id, None)
        logger.debug("MinHash deleted (memory): raw_id=%s", raw_id)

    def __len__(self) -> int:
        """Для моніторингу і тестів."""
        return len(self._store)


# ── Redis (production) ────────────────────────────────────────────────────────

class RedisMinHashRepository(IMinHashRepository):
    """
    Зберігає підписи в Redis як JSON.

    Args:
        redis: aioredis.Redis або redis.asyncio.Redis клієнт.
               Передається з container.py де він вже ініціалізований.

    TTL: _REDIS_TTL_SECONDS (7 днів) — після цього підпис автоматично видаляється.
    Це доцільно бо 7-денні статті вже не потраплять в feed в будь-якому разі.

    Пошук: SCAN + MGET — отримуємо всі ключі "minhash:*" і порівнюємо.
    Для 100k ключів це ~100-200ms. Якщо стане bottleneck — перейти на LSH.
    """

    def __init__(self, redis) -> None:
        self._redis = redis

    def _key(self, raw_id: UUID) -> str:
        return f"{_REDIS_KEY_PREFIX}{raw_id}"

    def _serialize(self, signature: MinHashSignature) -> str:
        return json.dumps({
            "signature": signature.signature,
            "num_perm": signature.num_perm,
        })

    def _deserialize(self, data: str | bytes) -> MinHashSignature:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        parsed = json.loads(data)
        return MinHashSignature(
            signature=parsed["signature"],
            num_perm=parsed["num_perm"],
        )

    async def save(self, raw_id: UUID, signature: MinHashSignature) -> None:
        key = self._key(raw_id)
        value = self._serialize(signature)
        await self._redis.setex(key, _REDIS_TTL_SECONDS, value)
        logger.debug("MinHash saved (redis): raw_id=%s ttl=%ds", raw_id, _REDIS_TTL_SECONDS)

    async def find_similar(
        self,
        signature: MinHashSignature,
        threshold: float,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        """
        SCAN по всіх ключах "minhash:*" + порівняння Jaccard.

        Підхід:
          1. SCAN щоб отримати всі ключі (не блокує Redis на відміну від KEYS)
          2. MGET батчем щоб мінімізувати round-trips
          3. Jaccard порівняння для кожного підпису
        """
        results: list[tuple[UUID, float]] = []
        batch_size = 200  # MGET батч

        # Збираємо всі ключі через SCAN (non-blocking)
        all_keys: list[str] = []
        cursor = 0
        pattern = f"{_REDIS_KEY_PREFIX}*"

        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )
            all_keys.extend(keys)
            if cursor == 0:
                break

        if not all_keys:
            return []

        # MGET батчами щоб не перевантажити Redis одним запитом
        for i in range(0, len(all_keys), batch_size):
            batch_keys = all_keys[i:i + batch_size]
            values = await self._redis.mget(*batch_keys)

            for key, value in zip(batch_keys, values):
                if value is None:
                    # TTL вже вийшов між SCAN і MGET — нормально
                    continue

                try:
                    stored_sig = self._deserialize(value)
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Corrupt MinHash entry key=%s: %s", key, exc)
                    continue

                if stored_sig.num_perm != signature.num_perm:
                    continue

                similarity = signature.jaccard(stored_sig)
                if similarity >= threshold:
                    # Витягуємо UUID з ключа: "minhash:{uuid}" → "{uuid}"
                    raw_id_str = key
                    if isinstance(key, bytes):
                        raw_id_str = key.decode("utf-8")
                    raw_id_str = raw_id_str.removeprefix(_REDIS_KEY_PREFIX)

                    try:
                        results.append((UUID(raw_id_str), similarity))
                    except ValueError:
                        logger.warning("Invalid UUID in Redis key: %s", raw_id_str)
                        continue

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def delete(self, raw_id: UUID) -> None:
        await self._redis.delete(self._key(raw_id))
        logger.debug("MinHash deleted (redis): raw_id=%s", raw_id)