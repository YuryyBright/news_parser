from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)

HEADERS_POOL = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ro,en;q=0.5",
    },
]

# Extensions that are never articles
_SKIP_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".rar", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".mp4", ".mp3",
}

# Path fragments skipped in heuristic (no-pattern) mode
_DEFAULT_SKIP_FRAGMENTS = (
    "/tag/", "/tags/", "/author/", "/page/",
    "/search", "/login", "/register",
    "/feed", "/rss", "/sitemap",
    "/contact", "/about", "/category/",
)


@dataclass
class _ListingItem:
    """Metadata harvested directly from the listing/hub page."""
    url: str
    title: str | None = None
    published_at: datetime | None = None


class WebPageFetcher(IFetcher):
    """
    Fetches a listing / hub page, collects article links (+ any metadata
    already present on the listing), then fetches and parses the body of
    each article — mirroring the RssFetcher contract.

    Two-phase approach
    ------------------
    Phase 1 — listing parse:
        • Collect URLs (same as before).
        • ALSO try to extract the title and date that many listing pages
          already embed next to each link (itemprop, data-date, <time>,
          sibling text, etc.).  When found, these values are kept as
          authoritative and are NOT overwritten by the article page.

    Phase 2 — article fetch (body only):
        • Fetch the article HTML and run trafilatura for the body text.
        • If Phase 1 gave us no title/date, fall back to extracting them
          from the article HTML (original behaviour).

    Configuration via Source.config dict (all keys optional):

        url_patterns    : list[str]   regex patterns matched against the full URL
        max_articles    : int         (default 50)
        concurrency     : int         (default 5)
        skip_body_fetch : bool        (default False) — set True to return only
                                      listing metadata without fetching article bodies.
                                      Useful when the listing already contains the
                                      full summary and you don't need the body.

    Examples
    --------
    # 1. Generic listing page — heuristic filter
    Source(url="https://www.financnasprava.sk/sk/pre-media/novinky")

    # 2. Hub page with targeted patterns — mapn.ro press office
    Source(
        url="https://www.mapn.ro/biroul_presa/index.php",
        config={
            "url_patterns": [r"mapn\\.ro/cpresa/\\d+"],
        },
    )
    """

    def __init__(
        self,
        timeout: float = 15.0,
        max_articles: int = 50,
        concurrency: int = 5,
    ) -> None:
        self._timeout = timeout
        self._default_max_articles = max_articles
        self._default_concurrency = concurrency

    # ------------------------------------------------------------------ #
    # HTML helpers                                                         #
    # ------------------------------------------------------------------ #

    def _clean_html(self, raw_html: str) -> str:
        """Strips HTML, preserving links as 'text (url)'."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            link_text = tag.get_text(strip=True)
            if link_text and link_text != href:
                tag.replace_with(f"{link_text} ({href})")
            elif href:
                tag.replace_with(f"({href})")
            else:
                tag.replace_with(link_text)
        return soup.get_text(separator=" ", strip=True).replace("\xa0", " ")

    # ------------------------------------------------------------------ #
    # Phase 1 — listing parse                                             #
    # ------------------------------------------------------------------ #

    def _extract_listing_items(self, html: str, base_url: str) -> list[_ListingItem]:
        """
        Walk every <a href> on the listing page and try to harvest title +
        date from the surrounding DOM context.

        Strategy (in priority order for title):
          1. Nearest <h1..h6> ancestor or sibling that contains the <a>
          2. The link text itself (if it looks like a real title, not a date/number)
          3. aria-label / title attribute on the <a>

        Strategy (in priority order for date):
          1. <time datetime="..."> near the link
          2. itemprop="datePublished" content attribute near the link
          3. data-date / data-published / data-time attribute near the link
          4. JSON-LD on the whole page (keyed by URL) — best-effort

        "Near" = within the same ancestor block (up to 4 levels up from <a>).
        """
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc
        seen: set[str] = set()
        items: list[_ListingItem] = []

        # Pre-parse JSON-LD for date fallback (url → date mapping)
        ld_dates: dict[str, datetime] = self._parse_ld_dates(soup)

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "mailto:", "javascript:")):
                continue

            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)

            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc != base_domain:
                continue
            if absolute.rstrip("/") == base_url.rstrip("/"):
                continue

            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS):
                continue

            norm = absolute.split("?")[0].split("#")[0].rstrip("/")
            if norm in seen:
                continue
            seen.add(norm)

            # ── title ────────────────────────────────────────────────────
            title = self._extract_title_near(a_tag)

            # ── date ─────────────────────────────────────────────────────
            published_at = (
                self._extract_date_near(a_tag)
                or ld_dates.get(norm)
                or ld_dates.get(absolute)
            )

            items.append(_ListingItem(url=absolute, title=title, published_at=published_at))

        return items

    def _block_ancestor(self, tag, max_levels: int = 4):
        """Walk up the DOM up to max_levels and return the highest block-level ancestor."""
        block_tags = {"div", "article", "section", "li", "tr", "td", "aside", "header", "main"}
        node = tag
        for _ in range(max_levels):
            parent = node.parent
            if parent is None or parent.name in ("[document]", "body", "html"):
                break
            node = parent
            if node.name in block_tags:
                break
        return node

    def _extract_title_near(self, a_tag) -> str | None:
        """Try to find the article title near an <a> tag."""
        block = self._block_ancestor(a_tag, max_levels=4)

        # 1. Nearest heading that contains (or IS a sibling of) the <a>
        for heading in block.find_all(re.compile(r"^h[1-6]$")):
            text = heading.get_text(strip=True)
            if text and len(text) > 10:
                return text

        # 2. The link text itself — accept if it looks like a real title
        link_text = a_tag.get_text(strip=True)
        if link_text and len(link_text) > 10 and not re.fullmatch(r"[\d\s/.,:-]+", link_text):
            return link_text

        # 3. aria-label or title attribute
        for attr in ("aria-label", "title"):
            val = a_tag.get(attr, "").strip()
            if val and len(val) > 10:
                return val

        return None

    def _extract_date_near(self, a_tag) -> datetime | None:
        """Try to find a publication date near an <a> tag."""
        block = self._block_ancestor(a_tag, max_levels=4)

        # 1. <time datetime="...">
        time_tag = block.find("time")
        if time_tag:
            dt = self._parse_iso(time_tag.get("datetime", "").strip())
            if dt:
                return dt
            # Some sites put the date as text inside <time>
            dt = self._parse_fuzzy_date(time_tag.get_text(strip=True))
            if dt:
                return dt

        # 2. itemprop="datePublished" (content attr or text)
        dp_tag = block.find(attrs={"itemprop": "datePublished"})
        if dp_tag:
            dt = (
                self._parse_iso(dp_tag.get("content", "").strip())
                or self._parse_fuzzy_date(dp_tag.get_text(strip=True))
            )
            if dt:
                return dt

        # 3. data-date / data-published / data-time on any element in block
        for candidate in block.find_all(True):
            for attr in ("data-date", "data-published", "data-time", "data-publish-date"):
                val = candidate.get(attr, "").strip()
                if val:
                    dt = self._parse_iso(val) or self._parse_fuzzy_date(val)
                    if dt:
                        return dt

        return None

    @staticmethod
    def _parse_fuzzy_date(value: str) -> datetime | None:
        """Handle common non-ISO date formats found on Eastern-European news sites."""
        if not value:
            return None
        # DD.MM.YYYY or DD-MM-YYYY
        m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", value)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                                tzinfo=timezone.utc)
            except ValueError:
                pass
        # YYYY-MM-DD plain
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                tzinfo=timezone.utc)
            except ValueError:
                pass
        return None

    def _parse_ld_dates(self, soup: BeautifulSoup) -> dict[str, datetime]:
        """Parse JSON-LD blocks and return {url: date} mapping."""
        result: dict[str, datetime] = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items: Iterable = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url") or item.get("@id") or ""
                    if not url:
                        continue
                    for key in ("datePublished", "dateCreated", "uploadDate"):
                        raw = item.get(key, "")
                        if raw:
                            dt = self._parse_iso(raw)
                            if dt:
                                result[url.rstrip("/")] = dt
                                break
            except (json.JSONDecodeError, AttributeError):
                continue
        return result

    # ------------------------------------------------------------------ #
    # Filtering                                                            #
    # ------------------------------------------------------------------ #

    def _filter_by_patterns(self, items: list[_ListingItem], patterns: list[str]) -> list[_ListingItem]:
        compiled = [re.compile(p) for p in patterns]
        return [item for item in items if any(rx.search(item.url) for rx in compiled)]

    def _is_likely_article(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return not any(frag in path for frag in _DEFAULT_SKIP_FRAGMENTS)

    # ------------------------------------------------------------------ #
    # Date extraction (article page fallback)                             #
    # ------------------------------------------------------------------ #

    def _extract_meta_date(self, html: str) -> datetime | None:
        soup = BeautifulSoup(html, "html.parser")

        for attrs in [
            {"property": "article:published_time"},
            {"name": "pubdate"},
            {"name": "DC.date"},
            {"itemprop": "datePublished"},
        ]:
            tag = soup.find("meta", attrs=attrs)
            if tag:
                dt = self._parse_iso(tag.get("content", "").strip())
                if dt:
                    return dt

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items: Iterable = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    for key in ("datePublished", "dateCreated", "uploadDate"):
                        raw = item.get(key, "")
                        if raw:
                            dt = self._parse_iso(raw)
                            if dt:
                                return dt
            except (json.JSONDecodeError, AttributeError):
                continue

        return None

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        if not value:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(value[:25], fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------ #
    # HTTP                                                                 #
    # ------------------------------------------------------------------ #

    async def _get_html(self, client: httpx.AsyncClient, url: str) -> str | None:
        headers = random.choice(HEADERS_POOL)
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return await self._trafilatura_fallback(url)
            logger.warning("WebPageFetcher: HTTP error %s: %s", url, exc)
            return None
        except Exception as exc:
            logger.warning("WebPageFetcher: failed to fetch %s: %s", url, exc)
            return None

    async def _trafilatura_fallback(self, url: str) -> str | None:
        loop = asyncio.get_running_loop()
        try:
            html = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url))
            return html or None
        except Exception as exc:
            logger.warning("WebPageFetcher: trafilatura fallback failed %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------ #
    # Phase 2 — article body fetch                                        #
    # ------------------------------------------------------------------ #

    async def _enrich_with_body(
        self,
        client: httpx.AsyncClient,
        item: _ListingItem,
        semaphore: asyncio.Semaphore,
    ) -> ParsedContent | None:
        """
        Fetch the article page, extract the body (and title/date if the
        listing didn't give us those), and return a ParsedContent.
        """
        async with semaphore:
            html = await self._get_html(client, item.url)

        if not html:
            # If we at least have a title from the listing, return without body.
            if item.title:
                logger.debug(
                    "WebPageFetcher: no HTML for %s, returning listing metadata only",
                    item.url,
                )
                return self._make_parsed_content(item, body="")
            return None

        loop = asyncio.get_running_loop()

        body_raw: str | None = await loop.run_in_executor(
            None,
            lambda: trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,
            ),
        )
        body = (body_raw or "").strip()

        # Fill in title / date from the article page only if listing didn't provide them
        title = item.title
        published_at = item.published_at

        if not title:
            soup = BeautifulSoup(html, "html.parser")
            h1_tag = soup.find("h1")
            title_tag = soup.find("title")
            raw_title = (
                (h1_tag.get_text(strip=True) if h1_tag else None)
                or (title_tag.get_text(strip=True) if title_tag else None)
                or ""
            )
            title = self._clean_html(raw_title)

        if not published_at:
            published_at = self._extract_meta_date(html)

        if not title:
            logger.debug("WebPageFetcher: skipping %s — no title", item.url)
            return None

        return self._make_parsed_content(
            _ListingItem(url=item.url, title=title, published_at=published_at),
            body=body,
        )

    def _make_parsed_content(self, item: _ListingItem, body: str) -> ParsedContent | None:
        try:
            return ParsedContent(
                title=item.title or "",
                body=body,
                url=item.url,
                published_at=item.published_at,
                language=None,
            )
        except Exception as exc:
            logger.warning("WebPageFetcher: invalid ParsedContent %s: %s", item.url, exc)
            return None

    # ------------------------------------------------------------------ #
    # Public interface — mirrors RssFetcher.fetch                         #
    # ------------------------------------------------------------------ #

    async def fetch(self, source: Source) -> list[ParsedContent]:
        # ── витягуємо config як dict ──────────────────────────────────────────
        raw_cfg = getattr(source, "config", None)
        if raw_cfg is None:
            cfg: dict = {}
        elif isinstance(raw_cfg, dict):
            cfg = raw_cfg
        else:
            # SourceConfig або будь-який інший об'єкт → беремо extra або __dict__
            cfg = (
                getattr(raw_cfg, "extra", None)
                or getattr(raw_cfg, "model_extra", None)  # pydantic v2
                or {}
            )
            # Додаємо стандартні поля SourceConfig явно, якщо extra порожній
            if not cfg and hasattr(raw_cfg, "__dict__"):
                cfg = {k: v for k, v in raw_cfg.__dict__.items()
                    if not k.startswith("_")}

        url_patterns: list[str] = cfg.get("url_patterns", [])
        max_articles: int = int(cfg.get("max_articles", self._default_max_articles))
        concurrency: int = int(cfg.get("concurrency", self._default_concurrency))
        skip_body_fetch: bool = bool(cfg.get("skip_body_fetch", False))
        semaphore = asyncio.Semaphore(concurrency)

        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            http2=True,
        ) as client:
            # ── Phase 1: parse listing ───────────────────────────────────
            index_html = await self._get_html(client, source.url)
            if not index_html:
                logger.warning("WebPageFetcher: could not fetch index %s", source.url)
                return []

            all_items = self._extract_listing_items(index_html, source.url)

            if url_patterns:
                candidate_items = self._filter_by_patterns(all_items, url_patterns)
                logger.info(
                    "WebPageFetcher: source=%s total_links=%d "
                    "pattern_matched=%d patterns=%s",
                    source.url, len(all_items), len(candidate_items), url_patterns,
                )
            else:
                candidate_items = [i for i in all_items if self._is_likely_article(i.url)]
                logger.info(
                    "WebPageFetcher: source=%s total_links=%d heuristic_ok=%d",
                    source.url, len(all_items), len(candidate_items),
                )

            candidate_items = candidate_items[:max_articles]

            # Log how much metadata we already have from the listing
            has_title = sum(1 for i in candidate_items if i.title)
            has_date = sum(1 for i in candidate_items if i.published_at)
            logger.info(
                "WebPageFetcher: listing metadata — title=%d/%d date=%d/%d",
                has_title, len(candidate_items), has_date, len(candidate_items),
            )

            if skip_body_fetch:
                # Return listing metadata only (no article page fetches)
                results = [
                    self._make_parsed_content(item, body="")
                    for item in candidate_items
                    if item.title
                ]
                logger.info(
                    "WebPageFetcher: skip_body_fetch=True, returning %d items", len(results)
                )
                return [r for r in results if r is not None]

            # ── Phase 2: enrich with article body ────────────────────────
            tasks = [
                self._enrich_with_body(client, item, semaphore)
                for item in candidate_items
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ParsedContent] = []
        for item in raw_results:
            if isinstance(item, ParsedContent):
                results.append(item)
            elif isinstance(item, Exception):
                logger.warning("WebPageFetcher: article task raised %s", item)

        logger.info(
            "WebPageFetcher: source=%s parsed_ok=%d (candidates=%d)",
            source.url, len(results), len(candidate_items),
        )
        return results