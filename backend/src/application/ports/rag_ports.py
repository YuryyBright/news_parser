# application/ports/rag_ports.py
"""
Порти (interfaces) для RAG-пайплайну.

Принцип залежностей (DIP):
  Use cases залежать від цих абстракцій.
  Infrastructure реалізує їх (ChromaDB, Anthropic API, файлова система).

Всі методи async — pipeline повністю асинхронний.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from src.domain.news_generation.entities import GeneratedNews, SearchResult, TextChunk


# ── IDocxParser ───────────────────────────────────────────────────────────────

class IDocxParser(ABC):
    """Читає .docx файл і повертає сирий текст."""

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """Синхронний (python-docx не async). Повертає весь текст документу."""
        ...


# ── ITextChunker ──────────────────────────────────────────────────────────────

class ITextChunker(ABC):
    """Розбиває текст на фрагменти."""

    @abstractmethod
    def chunk(self, text: str, source: str) -> list[TextChunk]:
        """Повертає список TextChunk. source — ім'я файлу або URL."""
        ...


# ── IEmbeddingService ─────────────────────────────────────────────────────────

class IEmbeddingService(ABC):
    """Отримує векторні представлення текстів."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Повертає список векторів (один на текст)."""
        ...

    @abstractmethod
    async def embed_one(self, text: str) -> np.ndarray:
        """Зручний метод для одного тексту."""
        ...


# ── IChunkVectorRepository ────────────────────────────────────────────────────

@dataclass
class ChunkRecord:
    """Запис для збереження в векторну БД."""
    chunk_id: str
    text: str
    embedding: np.ndarray
    source: str
    language: str
    metadata: dict


class IChunkVectorRepository(ABC):
    """CRUD для чанків у ChromaDB."""

    @abstractmethod
    async def upsert_batch(self, records: list[ChunkRecord]) -> None:
        """Зберігає або оновлює список чанків."""
        ...

    @abstractmethod
    async def query_similar(
        self,
        query_vector: np.ndarray,
        n_results: int = 10,
        language_filter: str | None = None,
    ) -> list[SearchResult]:
        """Семантичний пошук. language_filter — наприклад 'uk'."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Кількість чанків у колекції."""
        ...


# ── ILLMClient ────────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ILLMClient(ABC):
    """Клієнт для виклику LLM (Anthropic, OpenAI тощо)."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...


# ── IGeneratedNewsStorage ─────────────────────────────────────────────────────

class IGeneratedNewsStorage(ABC):
    """Зберігає згенеровані новини (файл або БД)."""

    @abstractmethod
    async def save(self, news: GeneratedNews) -> str:
        """Повертає шлях до файлу або ID в БД."""
        ...