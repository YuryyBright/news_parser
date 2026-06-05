# src/infrastructure/tagging/category_tagger.py
"""
CategoryTagger — перший шар тегування по фіксованих категоріях.

Маппінг BM25-тем → людськомовні теги:
  Категорії визначаються через BM25 (той самий корпус що у BM25ScoringService),
  тому не потрібен додатковий inference — просто переводимо topic_id у тег.

Додатково:
  - "Україна" — якщо є сигнальні слова у тексті
  - "соціальна політика" / "національна політика" — через keyword-правила
    (ці теми є частиною politics_government та minority_rights, але
     потребують окремого тегу для фронтенду)

Використання:
    tagger = CategoryTagger()
    tags = tagger.tag(full_text)
    # → ["прикордонно-міграційна", "Україна", "спецслужби"]
"""
from __future__ import annotations

import re
import logging
from typing import NamedTuple

import numpy as np

from src.infrastructure.scoring.vocabularies._loader import load_topic_corpus

logger = logging.getLogger(__name__)

# ── Маппінг topic_id → тег ────────────────────────────────────────────────────
_TOPIC_TAG_MAP: dict[int, str] = {
    0: "військова техніка",       # war_conflict
    1: "національна політика",    # politics_government
    2: "зовнішня політика",       # foreign_policy_nato
    3: "прикордонно-міграційна",  # border_migration
    4: "економіка та санкції",    # economy_sanctions
    5: "спецслужби",              # security_intelligence
    6: "права меншин",            # minority_rights
    7: "гуманітарна",             # humanitarian_warcrimes
    8: "транскордонна злочинність",  # cross_border_crime
    9: "кібербезпека",             # cybersecurity
}

# ── Keyword-правила для додаткових тегів ─────────────────────────────────────
# Формат: (тег, [сигнальні слова], мінімум збігів)
_KEYWORD_RULES: list[tuple[str, list[str], int]] = [
    (
        "Україна",
        [
            "ukraine", "ukrajna", "ukraina", "україна", "ukrainian",
            "ukrán", "ukrajinskí", "ucraina", "ucrainean",
            "zelenskyy", "zelenski", "kyiv", "київ", "kijów",
            "zakarpattia", "kárpátalja", "zakarpatsko", "transcarpatia",
            "donbas", "kharkiv", "odesa", "mariupol",
        ],
        1,
    ),
    (
        "соціальна політика",
        [
            # EN
            "social policy", "welfare", "pension", "healthcare", "education reform",
            "social benefit", "unemployment benefit", "minimum wage", "social spending",
            "public services", "housing policy", "social security",
            # HU
            "szociálpolitika", "nyugdíj", "egészségügy", "oktatás", "szociális ellátás",
            "minimálbér", "munkanélküli segély", "lakhatás", "közszolgáltatás",
            # SK
            "sociálna politika", "dôchodok", "zdravotníctvo", "vzdelávanie",
            "sociálne dávky", "minimálna mzda", "nezamestnanosť", "bývanie",
            # RO
            "politică socială", "pensie", "sănătate", "educație", "ajutor social",
            "salariu minim", "șomaj", "locuință",
        ],
        2,
    ),
    (
        "військова техніка",
        [
            # специфічна техніка — доповнює topic 0
            "tank", "танк", "tanc", "armored", "páncélos", "obrnený", "blindat",
            "f-16", "patriot", "himars", "leopard", "shahed", "drone", "дрон",
            "dron", "dronă", "vrtuľník", "helicopter", "helikopter",
            "missile", "raketa", "rakéta", "rachetă",
            "artillery", "artilerie", "artillería", "tüzérség", "delostrelectvo",
        ],
        2,
    ),

]

# ── Score-threshold для топік-тегу ────────────────────────────────────────────
_BM25_TAG_THRESHOLD = 0.15   # нормалізований score (0..1), нижче — не тегуємо
_BM25_MAX_SCORE     = 8.0


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    return [t for t in re.split(r"[\s\W]+", text) if len(t) > 2]


class CategoryTagger:
    """
    Тегер на основі BM25 + keyword-правил.
    Повертає list[str] — назви тегів для Article.add_tags().

    Сумісний з ITagger (duck typing): має метод .tag(text) -> list[str].
    """

    def __init__(self, bm25_max_score: float = _BM25_MAX_SCORE) -> None:
        self._max_score = bm25_max_score
        self._topic_tc  = load_topic_corpus()
        self._bm25      = self._build_bm25()

    def _build_bm25(self):
        try:
            from rank_bm25 import BM25Okapi
            return BM25Okapi(self._topic_tc.corpus)
        except ImportError:
            logger.warning("rank_bm25 not available — CategoryTagger uses keyword fallback only")
            return None

    def tag(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        text_lower = text.lower()
        result: set[str] = set()

        # ── 1. BM25 топік-теги ────────────────────────────────────────────────
        if self._bm25 is not None:
            tokens = _tokenize(text_lower)
            if tokens:
                scores = self._bm25.get_scores(tokens)
                static = scores[:len(self._topic_tc.corpus)]

                for topic_id, norm_score in enumerate(
                    (float(s) / self._max_score for s in static)
                ):
                    if norm_score >= _BM25_TAG_THRESHOLD and topic_id in _TOPIC_TAG_MAP:
                        result.add(_TOPIC_TAG_MAP[topic_id])
                        logger.debug(
                            "CategoryTagger BM25 tag: topic=%d/%s score=%.3f",
                            topic_id,
                            self._topic_tc.names.get(topic_id, "?"),
                            norm_score,
                        )
        else:
            # Fallback: keyword-підрахунок по корпусу
            for topic_id, keywords in enumerate(self._topic_tc.corpus):
                hits = sum(1 for kw in keywords if kw in text_lower)
                if hits >= 3 and topic_id in _TOPIC_TAG_MAP:
                    result.add(_TOPIC_TAG_MAP[topic_id])

        # ── 2. Keyword-правила (Україна, соціальна політика, тощо) ───────────
        for tag_name, signals, min_hits in _KEYWORD_RULES:
            hits = sum(1 for s in signals if s in text_lower)
            if hits >= min_hits:
                result.add(tag_name)
                logger.debug("CategoryTagger keyword tag: %s (hits=%d)", tag_name, hits)

        return sorted(result)  # стабільний порядок