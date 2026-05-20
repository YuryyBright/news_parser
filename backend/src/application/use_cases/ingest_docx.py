# application/use_cases/ingest_docx.py
"""
IngestDocxUseCase — пайплайн вхідної обробки .docx файлів.

Кроки:
  1. Парсинг тексту з .docx (IDocxParser)
  2. Чанкінг (ITextChunker)
  3. Embed кожного чанку (IEmbeddingService) — батчами
  4. Збереження у ChromaDB (IChunkVectorRepository)

DDD:
  ✅ orchestrates domain objects, не знає про HTTP або ORM
  ✅ залежить від портів, не від реалізацій
  ✅ повертає IngestResult DTO

Вже наявна інфраструктура:
  - EmbeddingService (той же що для article_vector_repo.py)
    → передається як IEmbeddingService через DI
  - ChromaDB AsyncClientWrapper (chroma_client.py)
    → ChunkVectorRepository використовує його напряму
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from src.application.ports.rag_ports import (
    IChunkVectorRepository,
    IDocxParser,
    IEmbeddingService,
    ITextChunker,
    ChunkRecord,
)
from src.domain.news_generation.entities import DocxSource, TextChunk

logger = logging.getLogger(__name__)

# Скільки чанків embedуємо за один API-виклик (обмеження моделі)
_EMBED_BATCH_SIZE = 32


@dataclass
class IngestResult:
    file_path: str
    total_chunks: int = 0
    saved_chunks: int = 0
    skipped_chunks: int = 0   # порожні або занадто короткі
    status: str = "ok"        # "ok" | "error"
    error: str = ""


class IngestDocxUseCase:
    """
    Читає один .docx файл і зберігає його чанки у векторну БД.

    Ідемпотентний: повторний запуск для того ж файлу
    перезапише чанки (upsert за chunk_id).
    """

    def __init__(
        self,
        parser: IDocxParser,
        chunker: ITextChunker,
        embedder: IEmbeddingService,
        chunk_repo: IChunkVectorRepository,
        min_chunk_length: int = 50,
    ) -> None:
        self._parser     = parser
        self._chunker    = chunker
        self._embedder   = embedder
        self._repo       = chunk_repo
        self._min_length = min_chunk_length

    async def execute(self, file_path: str) -> IngestResult:
        result = IngestResult(file_path=file_path)

        # ── 1. Парсинг ────────────────────────────────────────────────────────
        logger.info("[ingest] Reading file: %s", file_path)
        try:
            raw_text = self._parser.parse(file_path)
        except Exception as exc:
            logger.error("[ingest] Parse failed: %s → %s", file_path, exc)
            result.status = "error"
            result.error = str(exc)
            return result

        if not raw_text or not raw_text.strip():
            logger.warning("[ingest] Empty document: %s", file_path)
            result.status = "error"
            result.error = "Empty document"
            return result

        logger.info("[ingest] Parsed %d chars from %s", len(raw_text), file_path)

        # ── 2. Чанкінг ────────────────────────────────────────────────────────
        source_name = Path(file_path).name
        all_chunks  = self._chunker.chunk(raw_text, source=source_name)
        logger.info("[ingest] %d chunks from %s", len(all_chunks), source_name)

        # Фільтруємо занадто короткі
        valid_chunks = [c for c in all_chunks if c.is_valid and c.char_length >= self._min_length]
        result.skipped_chunks = len(all_chunks) - len(valid_chunks)
        result.total_chunks   = len(all_chunks)

        if not valid_chunks:
            logger.warning("[ingest] No valid chunks after filtering: %s", file_path)
            result.status = "error"
            result.error  = "No valid chunks"
            return result

        logger.info(
            "[ingest] Valid chunks: %d / %d (skipped %d short)",
            len(valid_chunks), len(all_chunks), result.skipped_chunks,
        )

        # ── 3. Embed (батчами) ────────────────────────────────────────────────
        records = await self._embed_chunks(valid_chunks, source_name)

        # ── 4. Збереження в ChromaDB ──────────────────────────────────────────
        try:
            await self._repo.upsert_batch(records)
            result.saved_chunks = len(records)
            logger.info("[ingest] Saved %d chunks for %s", len(records), source_name)
        except Exception as exc:
            logger.error("[ingest] Save failed for %s: %s", file_path, exc)
            result.status = "error"
            result.error  = str(exc)
            return result

        return result

    async def _embed_chunks(
        self,
        chunks: list[TextChunk],
        source_name: str,
    ) -> list[ChunkRecord]:
        """Embed всі чанки батчами, повертає список ChunkRecord."""
        records: list[ChunkRecord] = []
        texts = [c.text for c in chunks]

        for batch_start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch_texts  = texts[batch_start : batch_start + _EMBED_BATCH_SIZE]
            batch_chunks = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]

            logger.debug(
                "[ingest] Embedding batch %d–%d of %d",
                batch_start, batch_start + len(batch_texts), len(texts),
            )

            embeddings = self._embedder.embed(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                chunk_id = _make_chunk_id(source_name, chunk.chunk_index)
                records.append(ChunkRecord(
                    chunk_id=chunk_id,
                    text=chunk.text,
                    embedding=embedding,
                    source=chunk.source,
                    language=chunk.language,
                    metadata={
                        "chunk_index": chunk.chunk_index,
                        "char_length": chunk.char_length,
                        **chunk.metadata,
                    },
                ))

        return records


# ── Batch variant ─────────────────────────────────────────────────────────────

@dataclass
class BatchIngestResult:
    total_files:  int = 0
    ok_files:     int = 0
    failed_files: int = 0
    total_chunks: int = 0
    results: list[IngestResult] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        return {
            "total_files":  self.total_files,
            "ok_files":     self.ok_files,
            "failed_files": self.failed_files,
            "total_chunks": self.total_chunks,
        }


class BatchIngestDocxUseCase:
    """
    Обходить директорію або список файлів і інгестує кожен .docx.

    Кожен файл — незалежна операція. Помилка в одному файлі
    не зупиняє обробку решти.
    """

    def __init__(self, single_uc: IngestDocxUseCase) -> None:
        self._uc = single_uc

    async def execute_dir(self, directory: str) -> BatchIngestResult:
        """Знаходить всі .docx в директорії (рекурсивно) і інгестує."""
        paths = [
            str(p) for p in Path(directory).rglob("*.docx")
            if not p.name.startswith("~$")  # виключаємо тимчасові файли Word
        ]
        logger.info("[batch_ingest] Found %d .docx files in %s", len(paths), directory)
        return await self.execute_list(paths)

    async def execute_list(self, file_paths: list[str]) -> BatchIngestResult:
        batch = BatchIngestResult(total_files=len(file_paths))

        for path in file_paths:
            r = await self._uc.execute(path)
            batch.results.append(r)
            batch.total_chunks += r.saved_chunks

            if r.status == "ok":
                batch.ok_files += 1
            else:
                batch.failed_files += 1
                logger.warning("[batch_ingest] Failed: %s → %s", path, r.error)

        logger.info("[batch_ingest] Done: %s", batch.stats)
        return batch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chunk_id(source_name: str, chunk_index: int) -> str:
    """
    Детермінований ID для chunk — гарантує idempotency при upsert.
    Формат: "filename.docx::042"
    """
    safe_name = source_name.replace("/", "_").replace("\\", "_")
    return f"{safe_name}::{chunk_index:04d}"