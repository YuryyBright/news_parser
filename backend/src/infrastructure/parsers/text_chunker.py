# infrastructure/parsers/text_chunker.py

"""
SlidingWindowChunker та BlockAwareChunker — реалізують ITextChunker.

Стратегії:
  - "sliding_window": sliding window по реченнях з overlap (оригінальна логіка)
  - "block_aware":    блоки (абзаци, розділені \n\n) зберігаються цілими;
                      кілька блоків об'єднуються в чанк поки не досягнуто chunk_size,
                      але жоден блок ніколи не розривається посередині.

Параметри SlidingWindowChunker:
  chunk_size     — цільова к-сть символів на чанк (~500)
  overlap        — к-сть символів перекриття між чанками (~100)
  mode           — "sliding_window" | "block_aware"
  respect_blocks — якщо True (default), блоки ніколи не розриваються;
                   якщо False — поведінка оригінального sliding window.

Чому блоки важливіші за речення:
  У структурованих документах (новини, звіти, дайджести) абзац =
  одна думка / одна подія. Розрив посередині ламає семантику і погіршує
  якість відповідей RAG. Режим block_aware гарантує атомарність абзацу.
"""

from __future__ import annotations

import logging
import re
from enum import Enum

from src.application.ports.rag_ports import ITextChunker
from src.domain.news_generation.entities import TextChunk

logger = logging.getLogger(__name__)


class ChunkMode(str, Enum):
    SLIDING_WINDOW = "sliding_window"
    BLOCK_AWARE    = "block_aware"


class SlidingWindowChunker(ITextChunker):
    """
    Розбиває текст на чанки.

    Args:
        chunk_size:     цільова к-сть символів на чанк (default 500)
        overlap:        символів перекриття між сусідніми чанками (default 100,
                        використовується лише в режимі sliding_window)
        mode:           ChunkMode.SLIDING_WINDOW | ChunkMode.BLOCK_AWARE
        respect_blocks: якщо True — блоки (\n\n) ніколи не розриваються
                        (перевизначає mode і вмикає block_aware логіку для
                        граничних випадків навіть у sliding_window)
    """

    def __init__(
        self,
        chunk_size:     int       = 2000,
        overlap:        int       = 300,
        mode:           ChunkMode = ChunkMode.BLOCK_AWARE,
        respect_blocks: bool      = True,
    ) -> None:
        self._chunk_size     = chunk_size
        self._overlap        = overlap
        self._mode           = ChunkMode(mode)
        self._respect_blocks = respect_blocks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str, source: str) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        if self._mode == ChunkMode.BLOCK_AWARE or self._respect_blocks:
            return self._chunk_block_aware(text, source)
        return self._chunk_sliding_window(text, source)

    # ------------------------------------------------------------------
    # Block-aware strategy
    # ------------------------------------------------------------------

    def _chunk_block_aware(self, text: str, source: str) -> list[TextChunk]:
        """
        Блок (абзац, розділений \n\n) — атомарна одиниця.
        Кілька блоків об'єднуються в один чанк доки сума їх довжин
        не перевищує chunk_size. Щойно черговий блок не вміщається —
        поточний чанк зберігається і починається новий.

        Якщо окремий блок сам по собі довший за chunk_size:
          - він все одно потрапляє в окремий чанк цілим (не розривається).
          - у лог пишеться WARNING щоб можна було відстежити.
        """
        blocks = self._split_blocks(text)
        if not blocks:
            return []

        chunks:        list[TextChunk] = []
        current_parts: list[str]       = []
        current_len    = 0
        chunk_index    = 0

        for block in blocks:
            block_len = len(block)

            # Блок не вміщається до поточного акумулятора — зберігаємо чанк
            if current_parts and current_len + block_len > self._chunk_size:
                chunks.append(self._make_chunk(current_parts, chunk_index, source))
                chunk_index  += 1
                current_parts = []
                current_len   = 0

            # Блок сам по собі більший за chunk_size — кладемо окремим чанком
            if not current_parts and block_len > self._chunk_size:
                logger.warning(
                    "[chunker] block at source=%s exceeds chunk_size (%d > %d); "
                    "keeping intact as single chunk",
                    source, block_len, self._chunk_size,
                )
                chunks.append(TextChunk(
                    text=block,
                    chunk_index=chunk_index,
                    source=source,
                ))
                chunk_index += 1
                continue

            current_parts.append(block)
            current_len += block_len

        # Залишок
        if current_parts:
            chunks.append(self._make_chunk(current_parts, chunk_index, source))

        logger.debug(
            "[chunker:block_aware] %d chunks from %s (chunk_size=%d)",
            len(chunks), source, self._chunk_size,
        )
        return chunks

    # ------------------------------------------------------------------
    # Sliding-window strategy (оригінальна логіка, збережена)
    # ------------------------------------------------------------------

    def _chunk_sliding_window(self, text: str, source: str) -> list[TextChunk]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks:        list[TextChunk] = []
        current_parts: list[str]       = []
        current_len    = 0
        chunk_index    = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_len + sentence_len > self._chunk_size and current_parts:
                chunks.append(self._make_chunk(current_parts, chunk_index, source))
                chunk_index += 1

                # Overlap: залишаємо останні речення що вміщаються в overlap
                overlap_parts: list[str] = []
                overlap_len = 0
                for part in reversed(current_parts):
                    if overlap_len + len(part) <= self._overlap:
                        overlap_parts.insert(0, part)
                        overlap_len += len(part)
                    else:
                        break

                current_parts = overlap_parts
                current_len   = overlap_len

            current_parts.append(sentence)
            current_len += sentence_len

        if current_parts:
            chunks.append(self._make_chunk(current_parts, chunk_index, source))

        logger.debug(
            "[chunker:sliding_window] %d chunks from %s (chunk_size=%d, overlap=%d)",
            len(chunks), source, self._chunk_size, self._overlap,
        )
        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk(parts: list[str], index: int, source: str) -> TextChunk:
        return TextChunk(
            text="\n\n".join(parts).strip(),
            chunk_index=index,
            source=source,
        )

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        """
        Розбиває текст по подвійних переносах рядків (абзаци).
        Нормалізує внутрішні пробіли кожного блоку, але зберігає
        структуру між блоками.
        """
        raw_blocks = re.split(r"\n{2,}", text)
        blocks = []
        for b in raw_blocks:
            b = re.sub(r"[ \t]+", " ", b).strip()
            if b:
                blocks.append(b)
        return blocks

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """
        Простий sentence splitter на основі regex.
        Зберігає розділовий знак як частину попереднього речення.
        """
        text = re.sub(r"\s+", " ", text).strip()
        raw  = re.split(r"(?<=[.!?])\s+(?=[А-ЯЇІЄA-Z\d\"\(\[])", text)

        sentences: list[str] = []
        for part in raw:
            for sub in re.split(r"\n{2,}", part):
                sub = sub.strip()
                if sub:
                    sentences.append(sub)
        return sentences


# ---------------------------------------------------------------------------
# ParagraphChunker — без змін, альтернативна проста реалізація
# ---------------------------------------------------------------------------

class ParagraphChunker(ITextChunker):
    """
    Один абзац = один чанк.
    Простіший варіант; чанки можуть бути дуже різного розміру.
    Підходить для коротких документів де абзаци = окремі думки.
    """

    def __init__(self, min_length: int = 50) -> None:
        self._min_length = min_length

    def chunk(self, text: str, source: str) -> list[TextChunk]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks = []
        for i, para in enumerate(paragraphs):
            if len(para) >= self._min_length:
                chunks.append(TextChunk(
                    text=para,
                    chunk_index=i,
                    source=source,
                ))
        logger.debug("[paragraph_chunker] %d chunks from %s", len(chunks), source)
        return chunks