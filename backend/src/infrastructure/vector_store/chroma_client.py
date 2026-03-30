# infrastructure/vector_store/chroma_client.py
"""
ChromaDB клієнт — singleton з lazy ініціалізацією.

Правило імпортів:
  ✅ from config.settings import get_settings
  ❌ from src.config.container import get_settings  ← циклічний імпорт

Lazy init: клієнт створюється при ПЕРШОМУ виклику get_chroma(),
не при імпорті модуля. Це важливо — settings можуть ще не бути
завантажені на момент імпорту.
"""
from __future__ import annotations

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

_client: chromadb.AsyncClientAPI | None = None


def build_chroma_client() -> chromadb.AsyncClientAPI:
    """
    Будує Chroma клієнт відповідно до settings.

    Стратегія вибору:
      persist_dir + host==localhost → локальний persistent (dev/test)
      інакше → HTTP клієнт (production)
    """
    # Імпортуємо settings тут — не на рівні модуля
    from config.settings import get_settings
    cfg = get_settings().chroma

    if cfg.persist_dir and cfg.host == "localhost":
        logger.info("Chroma: local persistent client (dir=%s)", cfg.persist_dir)
        return chromadb.AsyncClient(
            settings=ChromaSettings(
                persist_directory=cfg.persist_dir,
                anonymized_telemetry=False,
            )
        )

    logger.info("Chroma: HTTP client (%s:%s)", cfg.host, cfg.port)
    return chromadb.AsyncHttpClient(
        host=cfg.host,
        port=cfg.port,
    )


async def get_chroma() -> chromadb.AsyncClientAPI:
    """
    Повертає singleton клієнт.
    Перший виклик — ініціалізує. Подальші — повертають той самий.
    """
    global _client
    if _client is None:
        _client = build_chroma_client()
    return _client


async def close_chroma() -> None:
    """Закрити з'єднання при shutdown. Викликати з Container.close()."""
    global _client
    if _client is not None:
        try:
            await _client.close()
        except Exception:
            pass  # не критично при shutdown
        finally:
            _client = None