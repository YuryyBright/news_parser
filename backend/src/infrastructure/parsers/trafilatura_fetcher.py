from __future__ import annotations

import asyncio
import logging
import random

import httpx
import trafilatura

from src.application.ports.article_content_fetcher import IArticleContentFetcher

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


class TrafilaturaContentFetcher(IArticleContentFetcher):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    async def fetch_full_text(self, url: str) -> str | None:
        headers = random.choice(HEADERS_POOL)

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                http2=True,
            ) as client:
                domain = httpx.URL(url).host
                await client.get(f"https://{domain}", headers=headers)

                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html = response.text

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return await self._fallback_trafilatura_fetch(url)
            logger.warning("ContentFetcher: failed to fetch %s: %s", url, exc)
            return None
        except Exception as exc:
            logger.warning("ContentFetcher: failed to fetch %s: %s", url, exc)
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,
            ),
        )

    async def _fallback_trafilatura_fetch(self, url: str) -> str | None:
        """Trafilatura має власний fetcher з кращим обходом блокувань."""
        loop = asyncio.get_running_loop()
        try:
            html = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url))
            if not html:
                logger.debug("Trafilatura fallback: empty response for %s", url)
                return None
            return await loop.run_in_executor(
                None,
                lambda: trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False,
                    favor_recall=True,
                ),
            )
        except Exception as exc:
            logger.warning("Trafilatura fallback failed for %s: %s", url, exc)
            return None