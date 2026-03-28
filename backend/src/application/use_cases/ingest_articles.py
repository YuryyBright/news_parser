# application/use_cases/ingest_articles.py
"""
FetchPipelineUseCase — Application Service.

У DDD Application Service (Use Case) — це тонкий оркестратор.
Він:
  1. отримує залежності (repos, domain services) через конструктор
  2. викликає доменні методи в правильному порядку
  3. керує транзакцією (через session.commit)
  4. НЕ містить бізнес-логіки сам по собі

Цей use case запускається автоматично при старті і потім periodically.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import (
    ArticleModel,
    RawArticleModel,
    FetchJobModel,
    SourceModel,
)
from infrastructure.persistence.repositories.article_repo import ArticleRepository

logger = logging.getLogger(__name__)


# ─── простий RSS-парсер (без зовнішніх залежностей) ─────────────────────────

async def _parse_rss(url: str) -> list[dict]:
    """
    Мінімальний RSS-парсер для демонстрації.
    В реальному проекті замінити на feedparser або aiohttp + lxml.
    """
    import aiohttp
    import xml.etree.ElementTree as ET

    try:
        async with aiohttp.ClientSession() as client:
            async with client.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
    except Exception as e:
        logger.warning(f"RSS fetch failed for {url}: {e}")
        return []

    try:
        root = ET.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []
        # RSS 2.0
        for item in root.findall(".//item"):
            items.append({
                "title":  (item.findtext("title") or "").strip(),
                "body":   (item.findtext("description") or "").strip(),
                "url":    (item.findtext("link") or "").strip(),
                "pub":    item.findtext("pubDate"),
            })
        # Atom
        for entry in root.findall(".//atom:entry", ns):
            link_el = entry.find("atom:link", ns)
            items.append({
                "title": (entry.findtext("atom:title", namespaces=ns) or "").strip(),
                "body":  (entry.findtext("atom:summary", namespaces=ns) or "").strip(),
                "url":   link_el.get("href", "") if link_el is not None else "",
                "pub":   entry.findtext("atom:published", namespaces=ns),
            })
        return items
    except ET.ParseError as e:
        logger.warning(f"XML parse error for {url}: {e}")
        return []


def _content_hash(title: str, body: str) -> str:
    """SHA-256 від title+body для дедуплікації."""
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()


# ─── Use Case ────────────────────────────────────────────────────────────────

class FetchPipelineUseCase:
    """
    Оркеструє повний цикл: завантажити → перевірити дублікати → зберегти.

    Після збереження статті з статусом 'pending' запускається
    EmbedAndScoreUseCase (можна в тій самій транзакції або окремо).
    """

    def __init__(
        self,
        session: AsyncSession,
        article_repo: ArticleRepository,
    ) -> None:
        self._session      = session
        self._article_repo = article_repo

    async def run_for_source(self, source: SourceModel) -> int:
        """
        Завантажити статті для одного джерела.
        Повертає кількість нових (не-дублікатів) статей.
        """
        logger.info(f"Fetching source: {source.name} ({source.url})")

        # 1. Створити FetchJob зі статусом 'running'
        job = FetchJobModel(
            source_id=source.id,
            status="running",
            last_run_at=datetime.now(timezone.utc),
        )
        self._session.add(job)
        await self._session.flush()

        try:
            # 2. Завантажити статті (RSS або інший тип)
            if source.source_type in ("rss", "atom"):
                raw_items = await _parse_rss(source.url)
            else:
                logger.info(f"Source type '{source.source_type}' not implemented yet")
                raw_items = []

            new_count = 0

            for item in raw_items:
                title = item.get("title", "")
                body  = item.get("body", "")
                url   = item.get("url", "")

                if not title or not url:
                    continue

                content_hash = _content_hash(title, body)

                # 3. Перевірка дублікатів за hash — якщо вже є, пропускаємо
                existing = await self._article_repo.get_by_hash(content_hash)
                if existing is not None:
                    continue

                # 4. Перевірка за URL — той самий контент міг прийти з іншого джерела
                existing_url = await self._article_repo.get_by_url(url)
                if existing_url is not None:
                    continue

                # 5. Зберегти RawArticle (сирий, до нормалізації)
                raw = RawArticleModel(
                    source_id=source.id,
                    title=title,
                    body=body,
                    url=url,
                    content_hash=content_hash,
                    language=None,
                    published_at=None,
                )
                self._session.add(raw)
                await self._session.flush()

                # 6. Зберегти нормалізовану Article зі статусом 'pending'
                #    Pipeline embedding/scoring підхопить її окремо
                article = ArticleRepository.build(
                    source_id=UUID(source.id),
                    raw_article_id=UUID(raw.id),
                    title=title,
                    body=body,
                    url=url,
                    content_hash=content_hash,
                    published_at=raw.published_at,
                )
                await self._article_repo.save(article)
                new_count += 1

            # 7. Оновити статус FetchJob
            job.status = "done"
            job.error_message = None
            await self._session.commit()

            logger.info(f"Source '{source.name}': {new_count} new articles saved")
            return new_count

        except Exception as e:
            await self._session.rollback()
            job.status = "failed"
            job.retries += 1
            job.error_message = str(e)
            await self._session.commit()
            logger.error(f"Fetch failed for source '{source.name}': {e}", exc_info=True)
            return 0