# infrastructure/container_rag.py
"""
RAG Pipeline DI Container.

Збирає всі залежності в одному місці.
Використовує НАЯВНУ інфраструктуру:
  - get_chroma()            (chroma_client.py)
  - get_settings()          (config/settings.py)
  - session_factory         (той самий що в ProcessArticlesUseCase)

Патерн: функції-фабрики (не singleton клас) — простіше і без магії.

Використання в FastAPI:
    from infrastructure.container_rag import build_rag_container
    rag = build_rag_container()

    # Use cases доступні через:
    rag.ingest_uc()
    rag.generate_uc()
    rag.verify_uc()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RagContainer:
    """
    Контейнер залежностей для RAG-пайплайну.

    Всі компоненти — lazy (ініціалізуються при першому зверненні).
    Виключення: chroma_client отримується ззовні (вже ініціалізований).
    """
    _chroma_client: Any
    _settings: Any
    _output_dir: str = "generated_news"

    # ── Інфраструктурні компоненти ────────────────────────────────────────────

    @cached_property
    def embedder(self):
        from infrastructure.scoring.embedding_service import (
            SentenceTransformerEmbeddingService,
        )
        cfg = self._settings.embedding
        return SentenceTransformerEmbeddingService(
            model_name=getattr(cfg, "model_name", "BAAI/bge-m3"),
            device=getattr(cfg, "device", None),
        )

    @cached_property
    def chunk_repo(self):
        from infrastructure.vector_store.chunk_vector_repo import ChunkVectorRepository
        cfg = self._settings
        col_name   = getattr(cfg.chroma, "collection_docx_chunks", "docx_chunks")
        dimensions = cfg.embedding.dimensions
        return ChunkVectorRepository(
            client=self._chroma_client,
            collection_name=col_name,
            dimensions=dimensions,
        )

    @cached_property
    def docx_parser(self):
        from infrastructure.parsers.docx_parser import DocxParser
        return DocxParser()

    @cached_property
    def chunker(self):
        from infrastructure.parsers.text_chunker import SlidingWindowChunker
        return SlidingWindowChunker(chunk_size=2000, overlap=300, mode="block_aware")

    @cached_property
    def llm_client(self):
        from infrastructure.llm.anthropic_client import AnthropicLLMClient
        cfg = self._settings
        api_key = getattr(cfg, "anthropic_api_key", None) or getattr(cfg, "llm", None)
        if not api_key:
            raise ValueError(
                "anthropic_api_key not found in settings. "
                "Add ANTHROPIC_API_KEY to .env"
            )
        return AnthropicLLMClient(api_key=api_key)

    @cached_property
    def news_storage(self):
        from infrastructure.storage.news_storage import MarkdownNewsStorage
        return MarkdownNewsStorage(output_dir=self._output_dir)

    # ── Use Cases ─────────────────────────────────────────────────────────────

    @cached_property
    def ingest_single_uc(self):
        from application.use_cases.ingest_docx import IngestDocxUseCase
        return IngestDocxUseCase(
            parser=self.docx_parser,
            chunker=self.chunker,
            embedder=self.embedder,
            chunk_repo=self.chunk_repo,
        )

    @cached_property
    def ingest_batch_uc(self):
        from application.use_cases.ingest_docx import BatchIngestDocxUseCase
        return BatchIngestDocxUseCase(single_uc=self.ingest_single_uc)

    @cached_property
    def generate_uc(self):
        from application.use_cases.generate_news import GenerateNewsUseCase
        return GenerateNewsUseCase(
            embedder=self.embedder,
            chunk_repo=self.chunk_repo,
            llm_client=self.llm_client,
            news_storage=self.news_storage,
        )

    @cached_property
    def verify_uc(self):
        from application.use_cases.verify_search import VerifySearchUseCase
        return VerifySearchUseCase(
            embedder=self.embedder,
            chunk_repo=self.chunk_repo,
        )


async def build_rag_container(output_dir: str = "generated_news") -> RagContainer:
    """
    Фабрика RAG контейнера.

    Використовує наявні синглтони:
      - get_chroma()     → AsyncClientWrapper (chroma_client.py)
      - get_settings()   → Settings (config/settings.py)

    Виклик:
        rag = await build_rag_container()
    """
    from src.infrastructure.vector_store.chroma_client import get_chroma
    from src.config.settings import get_settings

    chroma  = await get_chroma()
    settings = get_settings()

    logger.info("[rag_container] Initialized RAG container")
    return RagContainer(
        _chroma_client=chroma,
        _settings=settings,
        _output_dir=output_dir,
    )