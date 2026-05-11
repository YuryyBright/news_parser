"""
Ручний тест парсингу посилань через fetcher_factory / WebPageFetcher.

Запуск:
    python parse_link.py https://www.financnasprava.sk/sk/pre-media/novinky
    python parse_link.py https://www.mapn.ro/biroul_presa/index.php --patterns "cpresa/\\d+"
    python parse_link.py https://example.com/news --max 20
    python parse_link.py https://example.com/news --full   # також тягне body статей
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Мінімальні заглушки щоб не тягнути весь проект
# ---------------------------------------------------------------------------

@dataclass
class Source:
    url: str
    source_type: str = "web"
    config: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Тест парсингу посилань")
    parser.add_argument("url", help="URL сторінки-лістингу")
    parser.add_argument("--patterns", nargs="*", default=[], metavar="RE",
                        help="Regex-патерни для фільтрації посилань")
    parser.add_argument("--max", type=int, default=50, dest="max_articles",
                        help="Максимум посилань (default: 50)")
    parser.add_argument("--full", action="store_true",
                        help="Також завантажити body кожної статті (повільно)")
    args = parser.parse_args()

    source = Source(
        url=args.url,
        source_type="web",
        config={
            **({"url_patterns": args.patterns} if args.patterns else {}),
            "max_articles": args.max_articles,
        },
    )

    from src.infrastructure.parsers.fetcher_factory import build_fetcher
    from src.infrastructure.parsers.web_fetcher import HEADERS_POOL

    fetcher = build_fetcher(source)

    print(f"\n{'='*60}")
    print(f"URL:      {source.url}")
    print(f"Патерни:  {args.patterns or '(heuristic mode)'}")
    print(f"Ліміт:    {args.max_articles}")
    print(f"Режим:    {'full (listing + bodies)' if args.full else 'listing only'}")
    print(f"{'='*60}\n")

    import httpx
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, http2=True) as client:
        resp = await client.get(source.url, headers=random.choice(HEADERS_POOL))
        resp.raise_for_status()
        html = resp.text

    # ── Phase 1: listing items (url + title + date) ──────────────────────
    all_items = fetcher._extract_listing_items(html, source.url)
    print(f"Всього посилань на домені: {len(all_items)}")

    if args.patterns:
        filtered = fetcher._filter_by_patterns(all_items, args.patterns)
        mode = "pattern"
    else:
        filtered = [i for i in all_items if fetcher._is_likely_article(i.url)]
        mode = "heuristic"

    filtered = filtered[:args.max_articles]

    has_title = sum(1 for i in filtered if i.title)
    has_date  = sum(1 for i in filtered if i.published_at)
    print(f"Після фільтрації ({mode}):  {len(filtered)}")
    print(f"З заголовком з лістингу:   {has_title}/{len(filtered)}")
    print(f"З датою з лістингу:        {has_date}/{len(filtered)}\n")

    for idx, item in enumerate(filtered, 1):
        date_str  = item.published_at.strftime("%Y-%m-%d") if item.published_at else "—"
        title_str = (item.title or "—")[:80]
        print(f"  {idx:>3}. [{date_str}] {title_str}")
        print(f"       {item.url}")

    if not args.full:
        print(f"\n{'='*60}")
        print(f"Готово. {len(filtered)} посилань. Додайте --full щоб також тягнути body.")
        return

    # ── Phase 2: enrich with article bodies ──────────────────────────────
    print(f"\n{'='*60}")
    print("Завантажуємо body статей...\n")

    semaphore = asyncio.Semaphore(int(source.config.get("concurrency", 5)))

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, http2=True) as client:
        tasks = [fetcher._enrich_with_body(client, item, semaphore) for item in filtered]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    ok = 0
    for idx, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"  {idx:>3}. ERROR: {result}")
        elif result is None:
            print(f"  {idx:>3}. SKIP (no title)")
        else:
            body_preview = result.body[:120].replace("\n", " ") if result.body else "—"
            date_str = result.published_at.strftime("%Y-%m-%d") if result.published_at else "—"
            print(f"  {idx:>3}. [{date_str}] {result.title[:70]}")
            print(f"       body({len(result.body or '')} chars): {body_preview}")
            ok += 1

    print(f"\n{'='*60}")
    print(f"Готово. {ok}/{len(filtered)} статей успішно розпарсено.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)