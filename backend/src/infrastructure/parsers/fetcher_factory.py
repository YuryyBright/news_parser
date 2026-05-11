# src/infrastructure/parsers/fetcher_factory.py
"""
Фабрика фетчерів — єдине місце де вирішується який IFetcher використовувати.

Щоб додати новий тип:
  1. Реалізувати IFetcher у src/infrastructure/parsers/
  2. Додати SourceType.YOUR_TYPE у src/domain/ingestion/entities.py
  3. Додати elif гілку в build_fetcher() нижче — більше нічого чіпати не треба.

Поточні типи:
  rss  → RssFetcher        (feedparser, default)
  web  → WebPageFetcher    (listing/hub сторінки + trafilatura)
"""
from __future__ import annotations

from src.application.ports.fetcher import IFetcher
from src.domain.ingestion.entities import Source
import logging
logger = logging.getLogger(__name__)

def build_fetcher(source: Source) -> IFetcher:
    # source_type — окрема колонка БД, не всередині config JSON
    source_type = str(
        getattr(source, "source_type", None)           # ← пряме поле entity
        or getattr(source.config, "source_type", None) # ← fallback в config
        or "rss"
    ).lower()

    config_obj = getattr(source, "config", None)
    # url_patterns та інші параметри — в config JSON
    cfg: dict = {}
    if isinstance(config_obj, dict):
        cfg = config_obj
    elif config_obj is not None:
        cfg = getattr(config_obj, "extra", None) or getattr(config_obj, "__dict__", {})

    logger.info(
        "build_fetcher: source_type=%r cfg=%r",
        source_type, cfg,
    )

    if source_type == "web":
        from src.infrastructure.parsers.web_fetcher import WebPageFetcher
        return WebPageFetcher(
            timeout=float(cfg.get("timeout", 15.0)),
            max_articles=int(cfg.get("max_articles", 50)),
            concurrency=int(cfg.get("concurrency", 5)),
        )

    from src.infrastructure.parsers.rss_parser import RssFetcher
    return RssFetcher()