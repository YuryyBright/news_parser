import logging
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup  # Додаємо імпорт

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)

class RssFetcher(IFetcher):

    def _clean_html(self, raw_html: str) -> str:
        """Видаляє HTML-теги та нормалізує текст."""
        if not raw_html:
            return ""
        
        # Використовуємо lxml або html.parser
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Отримуємо текст, розділяючи блоки пробілами, щоб слова не зклеювалися
        # (наприклад, щоб </div><div> не перетворилося на "word1word2")
        text = soup.get_text(separator=" ", strip=True)
        
        # Додатково можна замінити нерозривні пробіли \xa0 на звичайні
        return text.replace("\xa0", " ")

    async def fetch(self, source: Source) -> list[ParsedContent]:
        # feedparser краще працює з URL напряму, але якщо потрібно async, 
        # зазвичай використовують httpx + feedparser.parse(response.text)
        feed = feedparser.parse(source.url)

        results: list[ParsedContent] = []
        for entry in feed.entries:
            # Очищуємо заголовок (буває, що там є &quot; або &amp;)
            raw_title = getattr(entry, "title", "").strip()
            title = self._clean_html(raw_title)

            url = getattr(entry, "link", "").strip()

            if not title or not url:
                logger.debug("Skipping entry without title or url: %s", entry)
                continue

            # Отримуємо сирий контент
            raw_body = (
                getattr(entry, "summary", "")
                or (getattr(entry, "content", [{}])[0].get("value", ""))
            ).strip()

            # ОЧИЩЕННЯ ТЕКСТУ ВІД ТЕГІВ
            body = self._clean_html(raw_body)

            published_at: datetime | None = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            try:
                content = ParsedContent(
                    title=title,
                    body=body,
                    url=url,
                    published_at=published_at,
                    language=None,
                )
                results.append(content)
            except Exception as exc:
                logger.warning("Skipping invalid entry url=%s: %s", url, exc)

        return results