# infrastructure/vector_store/chroma_client.py
"""
ChromaDB клієнт — singleton з lazy ініціалізацією.
Оновлено: додано AsyncWrapper для безпечної роботи локального клієнта в asyncio.
"""
from __future__ import annotations

import logging
import asyncio

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

_client = None

# ─── Async Wrappers for Local Sync Client ─────────────────────────────────────

class AsyncCollectionWrapper:
    """Wraps a synchronous ChromaDB Collection to be awaitable."""
    def __init__(self, collection):
        self._col = collection

    async def upsert(self, **kwargs):
        return await asyncio.to_thread(self._col.upsert, **kwargs)

    async def get(self, **kwargs):
        return await asyncio.to_thread(self._col.get, **kwargs)

    async def query(self, **kwargs):
        return await asyncio.to_thread(self._col.query, **kwargs)

    async def delete(self, **kwargs):
        return await asyncio.to_thread(self._col.delete, **kwargs)


class AsyncClientWrapper:
    """Wraps a synchronous ChromaDB Client to be awaitable."""
    def __init__(self, client):
        self._client = client

    async def get_or_create_collection(self, **kwargs):
        col = await asyncio.to_thread(self._client.get_or_create_collection, **kwargs)
        return AsyncCollectionWrapper(col)

    async def close(self):
        # PersistentClient doesn't require an async close
        pass

# ─── Client Builder ───────────────────────────────────────────────────────────

def build_chroma_client():
    """
    Будує Chroma клієнт відповідно до settings.
    """
    from src.config.settings import get_settings
    cfg = get_settings().chroma

    if cfg.persist_dir and cfg.host == "localhost":
        logger.info("Chroma: local persistent client wrapped for async (dir=%s)", cfg.persist_dir)
        
        # Ініціалізуємо синхронний клієнт
        sync_client = chromadb.PersistentClient(
            path=cfg.persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
            )
        )
        # Повертаємо обгортку, яка робить його сумісним з 'await'
        return AsyncClientWrapper(sync_client)

    logger.info("Chroma: HTTP client (%s:%s)", cfg.host, cfg.port)
    # Справжній асинхронний клієнт для production
    return chromadb.AsyncHttpClient(
        host=cfg.host,
        port=cfg.port,
    )

async def get_chroma():
    """Повертає singleton клієнт."""
    global _client
    if _client is None:
        _client = build_chroma_client()
    return _client

async def close_chroma() -> None:
    """Закрити з'єднання при shutdown."""
    global _client
    if _client is not None:
        try:
            if hasattr(_client, "close"):
                if asyncio.iscoroutinefunction(_client.close):
                    await _client.close()
                else:
                    _client.close()
        except Exception:
            pass
        finally:
            _client = None