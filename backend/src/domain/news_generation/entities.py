# domain/news_generation/entities.py
"""
Доменні сутності для RAG-пайплайну генерації новин.

Правила DDD:
  - Entities містять ідентифікатор і поведінку (не просто дані).
  - Value Objects — незмінні, рівність за значенням.
  - Жодної залежності від ORM, HTTP, ChromaDB тут немає.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


# ── Value Objects ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DocxSource:
    """Метадані файлу .docx — звідки прийшов документ."""
    file_path: str
    file_name: str
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TextChunk:
    """
    Фрагмент тексту після чанкінгу.

    chunk_index — порядковий номер в документі (для збереження послідовності).
    source      — звідки прийшов чанк (ім'я файлу / URL).
    language    — мова тексту (заповнюється після детекції, "unknown" за замовч.)
    """
    text: str
    chunk_index: int
    source: str
    language: str = "unknown"
    metadata: dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Чанк валідний якщо в ньому є реальний текст."""
        return bool(self.text and self.text.strip())

    @property
    def char_length(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class SearchResult:
    """Результат пошуку в векторній БД."""
    chunk_id: str           # id в ChromaDB
    text: str
    similarity_score: float  # 0.0 – 1.0
    source: str
    language: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0

    @property
    def passes_threshold(self, threshold: float = 0.85) -> bool:
        return self.similarity_score >= threshold


# ── Enums ─────────────────────────────────────────────────────────────────────

class GenerationStatus(StrEnum):
    PENDING   = "pending"
    GENERATED = "generated"
    FAILED    = "failed"
    SKIPPED   = "skipped"   # не вистачило контексту


# ── Aggregate Root ────────────────────────────────────────────────────────────

@dataclass
class GeneratedNews:
    """
    Aggregate Root — згенерована новина.

    Зберігається в БД або як .md / .docx файл.
    Містить посилання на чанки-джерела (traceability).
    """
    id: UUID
    title: str
    body: str
    source_chunks: list[str]    # chunk_id з ChromaDB — для трасування
    query: str                   # запит, за яким шукали контекст
    status: GenerationStatus
    language: str = "uk"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: str = ""
    context_score: float = 0.0  # середній similarity_score джерел

    @classmethod
    def create(
        cls,
        title: str,
        body: str,
        query: str,
        source_chunks: list[str],
        context_score: float = 0.0,
        model_used: str = "",
        language: str = "uk",
    ) -> "GeneratedNews":
        return cls(
            id=uuid4(),
            title=title,
            body=body,
            query=query,
            source_chunks=source_chunks,
            context_score=context_score,
            status=GenerationStatus.GENERATED,
            model_used=model_used,
            language=language,
        )

    @classmethod
    def skipped(cls, query: str, reason: str = "") -> "GeneratedNews":
        return cls(
            id=uuid4(),
            title="",
            body=reason,
            query=query,
            source_chunks=[],
            status=GenerationStatus.SKIPPED,
        )