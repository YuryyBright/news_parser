"""
VocabularyLoader — завантажує словники з YAML-файлів.

Кешує результат — повторні виклики не читають диск.
Виклик reload_all() інвалідує кеш без рестарту сервісу.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import yaml

logger = logging.getLogger(__name__)

_VOCAB_DIR = Path(__file__).parent


class NegativeKeywordsConfig(NamedTuple):
    keywords: list[str]
    penalty: float
    reject_threshold: int
    category_overrides: dict[int, dict]  # {cat_id: {reject_threshold: N}}


class BoostKeywordsConfig(NamedTuple):
    keywords: list[str]
    bonus: float
    max_hits: int


class TopicCorpus(NamedTuple):
    corpus: list[list[str]]           # індексований список токенів по темах
    names: dict[int, str]             # {topic_id: topic_name} для логів


@lru_cache(maxsize=1)
def load_negative_keywords() -> NegativeKeywordsConfig:
    """
    Повертає конфіг негативних ключових слів.

    keywords  — плоский список антислів (всі мови разом)
    penalty   — штраф за 1 хіт
    reject_threshold — глобальний поріг відхилення (>= N hits → score 0.0)
    category_overrides — {cat_id: {reject_threshold: N}} для виняткових категорій
    """
    path = _VOCAB_DIR / "negative_keywords.yaml"
    data = _load_yaml(path)

    flat: list[str] = []
    for group in data["keywords"].values():
        for lang_words in group.values():
            flat.extend(lang_words)

    # category_overrides: ключі з YAML приходять як int якщо числові
    raw_overrides = data.get("category_overrides", {})
    overrides = {int(k): v for k, v in raw_overrides.items()}

    return NegativeKeywordsConfig(
        keywords=flat,
        penalty=float(data["penalty"]),
        reject_threshold=int(data["reject_threshold"]),
        category_overrides=overrides,
    )


@lru_cache(maxsize=1)
def load_boost_keywords() -> BoostKeywordsConfig:
    """
    Повертає конфіг буст-слів.

    keywords — список буст-слів
    bonus    — бонус за хіт
    max_hits — максимум врахованих хітів
    """
    path = _VOCAB_DIR / "boost_keywords.yaml"
    data = _load_yaml(path)
    return BoostKeywordsConfig(
        keywords=data["keywords"],
        bonus=float(data["bonus"]),
        max_hits=int(data["max_hits"]),
    )


@lru_cache(maxsize=1)
def load_topic_corpus() -> TopicCorpus:
    """
    Повертає TopicCorpus:
      corpus — список корпусів тем, відсортований за meta.id.
               Кожен корпус — плоский список токенів (усі мови разом).
      names  — {topic_id: topic_name} для зручного логування.

    Приклад використання:
        tc = load_topic_corpus()
        bm25 = BM25Okapi(tc.corpus)
        logger.info("best topic: %s", tc.names[best_idx])
    """
    topics_dir = _VOCAB_DIR / "topics"
    topic_files = sorted(topics_dir.glob("*.yaml"))

    topics: list[tuple[int, str, list[str]]] = []
    for path in topic_files:
        data = _load_yaml(path)
        topic_id = int(data["meta"]["id"])
        topic_name = str(data["meta"]["name"])
        flat: list[str] = []
        for lang_words in data["keywords"].values():
            flat.extend(lang_words)
        topics.append((topic_id, topic_name, flat))
        logger.debug(
            "Loaded topic %d (%s): %d tokens",
            topic_id, topic_name, len(flat),
        )

    topics.sort(key=lambda x: x[0])
    return TopicCorpus(
        corpus=[words for _, _, words in topics],
        names={tid: name for tid, name, _ in topics},
    )


def reload_all() -> None:
    """
    Інвалідує кеш — наступний виклик перечитає всі файли з диска.
    Корисно при гарячому оновленні словників без рестарту сервісу.
    """
    load_negative_keywords.cache_clear()
    load_boost_keywords.cache_clear()
    load_topic_corpus.cache_clear()
    logger.info("Vocabulary cache cleared — next call will reload from disk")


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)