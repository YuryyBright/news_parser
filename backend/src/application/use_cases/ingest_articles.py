# application/use_cases/ingest_article.py
"""
IngestArticleUseCase — прийом нової статті з парсера.

Дедуплікація відбувається тут, ПЕРЕД збереженням:
  1. exists_by_url()  — точний збіг URL
  2. exists_by_hash() — збіг контенту (sha256 title+body)

Якщо стаття вже є — повертаємо DuplicateArticleResult.
Якщо нова — зберігаємо як RawArticle зі статусом "pending"
і ставимо задачу process_articles в чергу.

Dependency rule:
  ✅ domain interfaces (IRawArticleRepository)
  ✅ application dtos
  ❌ НЕ знає про SQLAlchemy, HTTP, Chroma
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import auto, Enum

from domain.ingestion.entities import RawArticle
from domain.ingestion.repositories import IRawArticleRepository
from domain.ingestion.value_objects import ParsedContent
from application.ports.task_queue import ITaskQueue

logger = logging.getLogger(__name__)


class IngestResult(Enum):
    SAVED     = auto()   # нова стаття збережена
    DUPLICATE = auto()   # стаття вже існує (url або hash)


@dataclass(frozen=True)
class IngestArticleCommand:
    source_id: object          # UUID
    title: str
    body: str
    url: str
    published_at: object       # datetime | None
    language: str | None = None


@dataclass(frozen=True)
class IngestArticleResult:
    status: IngestResult
    raw_article_id: object | None = None   # UUID, None якщо duplicate


class IngestArticleUseCase:
    """
    Приймає одну статтю від парсера та вирішує: зберегти чи відкинути.

    Використовується всередині handle_ingest_source worker'а.
    Один парсинг source → N викликів IngestArticleUseCase.
    """

    def __init__(
        self,
        raw_article_repo: IRawArticleRepository,
        task_queue: ITaskQueue,
    ) -> None:
        self._raw = raw_article_repo
        self._queue = task_queue

    async def execute(self, cmd: IngestArticleCommand) -> IngestArticleResult:
        content_hash = _compute_hash(cmd.title, cmd.body)

        # ── Дедуплікація рівень 1: URL ────────────────────────────────────────
        if await self._raw.exists_by_url(cmd.url):
            logger.debug("Duplicate URL skipped: %s", cmd.url)
            return IngestArticleResult(status=IngestResult.DUPLICATE)

        # ── Дедуплікація рівень 2: content hash ───────────────────────────────
        if await self._raw.exists_by_hash(content_hash):
            logger.debug("Duplicate content hash skipped: url=%s", cmd.url)
            return IngestArticleResult(status=IngestResult.DUPLICATE)

        # ── Зберігаємо нову статтю ────────────────────────────────────────────
        content = ParsedContent(
            title=cmd.title,
            body=cmd.body,
            url=cmd.url,
            published_at=cmd.published_at,
            language=cmd.language,
        )
        raw_article = RawArticle(source_id=cmd.source_id, content=content)
        raw_article.mark_ingested()

        await self._raw.save(raw_article)

        logger.info("Article ingested: id=%s url=%s", raw_article.id, cmd.url)

        # ── Запускаємо обробку ────────────────────────────────────────────────
        # Не чекаємо — просто ставимо в чергу
        await self._queue.enqueue(
            "process_articles",
            raw_article_id=str(raw_article.id),
        )

        return IngestArticleResult(
            status=IngestResult.SAVED,
            raw_article_id=raw_article.id,
        )


def _compute_hash(title: str, body: str) -> str:
    """SHA-256 від title+body. Однаковий алгоритм у repo і use case."""
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()