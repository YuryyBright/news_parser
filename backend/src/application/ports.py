# application/ports.py
"""
Інтерфейси (порти) — application шар визначає ЩО потрібно,
infrastructure реалізує ЯК це робиться.

Application НІКОЛИ не імпортує з infrastructure!
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
import numpy as np


# ─── Value objects для передачі між шарами ───────────────────────────────────

@dataclass(frozen=True)
class SourceDTO:
    id: UUID
    name: str
    url: str
    source_type: str
    config: dict
    fetch_interval_sec: int
    is_active: bool

@dataclass(frozen=True)
class RawArticleDTO:
    id: UUID
    source_id: UUID | None
    title: str
    body: str
    url: str
    language: str | None
    content_hash: str
    published_at: datetime | None

@dataclass(frozen=True)
class ArticleDTO:
    id: UUID
    source_id: UUID | None
    raw_article_id: UUID | None
    title: str
    body: str
    url: str
    language: str
    status: str
    relevance_score: float
    content_hash: str
    published_at: datetime | None


# ─── Репозиторії (порти) ─────────────────────────────────────────────────────

class ISourceRepository(ABC):
    @abstractmethod
    async def get_all_active(self) -> list[SourceDTO]: ...

    @abstractmethod
    async def get_by_id(self, source_id: UUID) -> SourceDTO | None: ...

    @abstractmethod
    async def save(self, source: SourceDTO) -> None: ...


class IRawArticleRepository(ABC):
    @abstractmethod
    async def save(self, article: RawArticleDTO) -> RawArticleDTO: ...

    @abstractmethod
    async def exists_by_hash(self, content_hash: str) -> bool: ...

    @abstractmethod
    async def get_unprocessed(self, limit: int = 100) -> list[RawArticleDTO]: ...


class IArticleRepository(ABC):
    @abstractmethod
    async def save(self, article: ArticleDTO) -> ArticleDTO: ...

    @abstractmethod
    async def exists_by_url(self, url: str) -> bool: ...

    @abstractmethod
    async def get_pending(self, limit: int = 100) -> list[ArticleDTO]: ...

    @abstractmethod
    async def update_status(self, article_id: UUID, status: str) -> None: ...

    @abstractmethod
    async def update_relevance_score(self, article_id: UUID, score: float) -> None: ...


class IFetchJobRepository(ABC):
    @abstractmethod
    async def create(self, source_id: UUID) -> UUID: ...

    @abstractmethod
    async def mark_running(self, job_id: UUID) -> None: ...

    @abstractmethod
    async def mark_done(self, job_id: UUID) -> None: ...

    @abstractmethod
    async def mark_failed(self, job_id: UUID, error: str) -> None: ...


# ─── Сервіси (порти) ─────────────────────────────────────────────────────────

class ITaskQueue(ABC):
    @abstractmethod
    async def enqueue(self, task_name: str, *args: Any, **kwargs: Any) -> str:
        """Повертає task_id."""
        ...

    @abstractmethod
    async def get_status(self, task_id: str) -> str:
        """Статус: 'pending' | 'in_progress' | 'completed' | 'failed'."""
        ...


class IEmbeddingService(ABC):
    @abstractmethod
    async def encode(self, texts: list[str]) -> np.ndarray:
        """Повертає матрицю (N, dim) float32."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class ILLMService(ABC):
    @abstractmethod
    async def generate_criteria_phrases(
        self, user_prompt: str, count: int
    ) -> list[str]: ...


class IArticleVectorRepository(ABC):
    @abstractmethod
    async def upsert(self, article_id: UUID, vector: np.ndarray, model_version: str) -> None: ...

    @abstractmethod
    async def query_similar(
        self, query_vector: np.ndarray, n_results: int = 10
    ) -> list[tuple[UUID, float]]: ...


class IFetcher(ABC):
    """Адаптер для конкретного типу джерела (RSS, HTML scraper тощо)."""

    @abstractmethod
    async def fetch(self, source: SourceDTO) -> list[RawArticleDTO]:
        """Повертає нові сирі статті з джерела."""
        ...