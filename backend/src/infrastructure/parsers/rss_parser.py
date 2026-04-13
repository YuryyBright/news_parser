import logging
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)


class RssFetcher(IFetcher):

    def _clean_html(self, raw_html: str) -> str:
        """
        Очищає HTML: зберігає текст і посилання у форматі 'текст (https://url)'.

        Приклад:
          <a href="https://example.com">138 місць</a> у парламенті
          → "138 місць (https://example.com) у парламенті"

        Посилання без тексту (або де текст == url) — залишаємо тільки url.
        """
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")

        # Замінюємо <a href="url">текст</a> → "текст (url)" прямо в дереві
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            link_text = tag.get_text(strip=True)
            if link_text and link_text != href:
                tag.replace_with(f"{link_text} ({href})")
            elif href:
                tag.replace_with(f"({href})")
            else:
                tag.replace_with(link_text)

        text = soup.get_text(separator=" ", strip=True)
        return text.replace("\xa0", " ")

    def _extract_url(self, entry) -> str:
        """
        Витягує URL з entry з fallback-ланцюжком:
          1. entry.link              — стандартний <link> тег
          2. entry.id                — feedparser парсить <guid> сюди
          3. entry.guid              — прямий доступ до <guid>
          4. перший enclosure        — для подкастів/медіа

        Повертає порожній рядок якщо нічого не знайдено.
        """
        # 1. Стандартний link
        url = getattr(entry, "link", "").strip()
        if url:
            return url

        # 2. feedparser кладе <guid> у entry.id
        url = getattr(entry, "id", "").strip()
        if url and url.startswith("http"):
            return url

        # 3. Прямий атрибут guid (деякі версії feedparser)
        url = getattr(entry, "guid", "").strip()
        if url and url.startswith("http"):
            return url

        # 4. Enclosures (медіа RSS)
        enclosures = getattr(entry, "enclosures", [])
        if enclosures:
            href = enclosures[0].get("href", "").strip()
            if href:
                return href

        return ""

    def _extract_body(self, entry) -> str:
        """
        Витягує тіло статті з fallback-ланцюжком:
        1. content:encoded  (повна стаття)
        2. summary          (короткий опис / може містити HTML)
        3. description      (entry.description — feedparser-псевдонім summary,
                            але деякі парсери кладуть його окремо)
        4. media_description (media:description із media:group або прямий атрибут)
        5. порожній рядок
        """
        # 1. content:encoded — повна стаття
        content_list = getattr(entry, "content", [])
        if content_list:
            value = content_list[0].get("value", "").strip()
            if value:
                return value

        # 2. summary — короткий опис
        summary = getattr(entry, "summary", "").strip()
        if summary:
            return summary

        # 3. description — у деяких фідах feedparser кладе сюди окремий текст
        description = getattr(entry, "description", "").strip()
        if description:
            return description

        # 4. media:description — YouTube, подкасти, media RSS
        #    feedparser розкладає media:group/media:description у media_description
        media_desc = getattr(entry, "media_description", "").strip()
        if media_desc:
            return media_desc

        # Fallback через media_content (деякі YouTube-фіди)
        for media in getattr(entry, "media_content", []):
            desc = media.get("description", "").strip()
            if desc:
                return desc

        return ""

    async def fetch(self, source: Source) -> list[ParsedContent]:
        feed = feedparser.parse(source.url)

        # Діагностика: якщо цифри тут менші за очікувані — проблема у feedparser
        # Якщо тут правильна кількість — проблема у дедуплікації вище (БД/use case)
        logger.info(
            'RssFetcher: source=%s total_in_feed=%d bozo=%s',
            source.url, len(feed.entries), feed.get('bozo', False),
        )

        results: list[ParsedContent] = []
        for entry in feed.entries:
            raw_title = getattr(entry, "title", "").strip()
            title = self._clean_html(raw_title)

            url = self._extract_url(entry)

            if not title or not url:
                logger.debug(
                    "Skipping entry without title or url | title=%r url=%r entry_id=%r",
                    title, url, getattr(entry, "id", "?"),
                )
                continue

            raw_body = self._extract_body(entry)
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

        logger.info(
            'RssFetcher: source=%s parsed_ok=%d (feed had %d)',
            source.url, len(results), len(feed.entries),
        )
        return results