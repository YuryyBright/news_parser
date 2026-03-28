# infrastructure/vector_store/chroma_client.py
from __future__ import annotations
import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config.container import get_settings
settings = get_settings()


def build_chroma_client() -> chromadb.AsyncHttpClient | chromadb.AsyncClientAPI:
    cfg = settings.chroma
    if cfg.persist_dir and cfg.host == "localhost":
        # Локальний persistent клієнт (dev/test)
        return chromadb.AsyncClient(
            settings=ChromaSettings(
                persist_directory=cfg.persist_dir,
                anonymized_telemetry=False,
            )
        )
    # Remote HTTP клієнт (production)
    return chromadb.AsyncHttpClient(
        host=cfg.host,
        port=cfg.port,
    )


_client: chromadb.AsyncClientAPI | None = None


async def get_chroma() -> chromadb.AsyncClientAPI:
    global _client
    if _client is None:
        _client = build_chroma_client()
    return _client