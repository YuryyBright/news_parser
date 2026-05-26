"""
BM25ScoringService — перший шар scoring (pre-filter).

Юзкейс: прикордонна зона UA/HU/SK/RO.
  Мови корпусу: HU + SK + RO + EN (UA видалено).
  Тематики: тільки те що визначає міграційну, прикордонну,
  внутрішню і зовнішню політику країн регіону + армія + економіка.

НЕ входить у корпус:
  - спорт, культура, виставки, розваги
  - кримінальна хроніка без політичного контексту
  - місцеві новини без регіонального/міжнародного виміру

Теми (9 категорій):
  0. war_conflict          — армія, фронт, зброя, мобілізація
  1. politics_government   — вибори, уряд, президент, парламент, корупція
  2. foreign_policy_nato   — НАТО, ЄС, двосторонні відносини, саміти
  3. border_migration      — кордон, міграція, біженці, транзит, пропускний пункт
  4. economy_sanctions     — ВВП, санкції, торгівля, енергетика, бюджет
  5. security_intelligence — спецслужби, гібридна війна, шпигунство, тероризм
  6. minority_rights       — права меншин, мовний закон, автономія (HU↔UA/SK/RO контекст)
  7. humanitarian_warcrimes— воєнні злочини, біженці з UA, гуманітарна допомога
  8. cross_border_crime    — контрабанда, наркотики, зброя, ОЗГ, митниця

Словники зберігаються у YAML-файлах (vocabularies/).
Для перезавантаження без рестарту: vocabularies._loader.reload_all()

Бібліотека: rank_bm25 (pip install rank-bm25)
  Якщо недоступна — fallback на SimpleKeywordScoring.
"""
from __future__ import annotations

import logging
import re

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

from src.infrastructure.scoring.vocabularies._loader import (
    load_negative_keywords,
    load_boost_keywords,
    load_topic_corpus,
)

logger = logging.getLogger(__name__)

# ─── Завантажуємо конфіги з YAML (кешовано через lru_cache) ──────────────────
_NEG_CFG   = load_negative_keywords()
_BOOST_CFG = load_boost_keywords()
_TOPIC_TC  = load_topic_corpus()

_NEGATIVE_KEYWORDS: list[str]     = _NEG_CFG.keywords
_NEGATIVE_PENALTY:  float         = _NEG_CFG.penalty
_BOOST_KEYWORDS:    list[str]     = _BOOST_CFG.keywords
_BOOST_BONUS:       float         = _BOOST_CFG.bonus
_BOOST_MAX_HITS:    int           = _BOOST_CFG.max_hits
_TOPIC_CORPUS_RAW:  list[list[str]] = _TOPIC_TC.corpus
_TOPIC_NAMES:       dict[int, str]  = _TOPIC_TC.names

_BM25_MAX_SCORE = 8.0

# Індекси динамічних кластерів (Рівень 3, якщо corpus_manager активний)
_CAT_USER_INTERESTS  = 9
_CAT_USER_ANTITOPICS = 10


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.split(r"[\s\W]+", text)
    return [t for t in tokens if len(t) > 2]


def _neg_reject_threshold(cat_id: int) -> int:
    """
    Повертає поріг відхилення для категорії.
    Використовує category_overrides з negative_keywords.yaml,
    fallback на глобальний reject_threshold.
    """
    override = _NEG_CFG.category_overrides.get(cat_id)
    if override:
        return int(override.get("reject_threshold", _NEG_CFG.reject_threshold))
    return _NEG_CFG.reject_threshold


class BM25ScoringService(IScoringService):
    """
    IScoringService через BM25 без geo-фільтрації.

    Корпус: 9 тем × 4 мови (HU/SK/RO/EN).
    Без UA — система орієнтована на регіональні медіа HU/SK/RO
    та англомовні джерела про регіон.

    ParsedContent.language НЕ використовується —
    корпус сам покриває всі 4 мови.

    Словники: vocabularies/*.yaml (оновлення без рестарту через reload_all()).
    """

    def __init__(self, max_score: float = _BM25_MAX_SCORE, corpus_manager=None) -> None:
        self._max_score = max_score
        self._corpus_manager = corpus_manager
        self._bm25 = self._build_bm25()

    def _build_bm25(self):
        # Якщо є corpus_manager — він вже побудував BM25 при ініціалізації
        if self._corpus_manager is not None:
            self._backend = "rank_bm25"
            return self._corpus_manager.get_bm25()
        # Fallback — статичний корпус
        try:
            from rank_bm25 import BM25Okapi
            self._backend = "rank_bm25"
            return BM25Okapi(_TOPIC_CORPUS_RAW)
        except ImportError:
            logger.warning("rank_bm25 not available — falling back to SimpleKeywordScoring")
            self._backend = "simple"
            return None

    def _get_live_bm25(self):
        """Завжди повертає актуальний BM25 (після можливого rebuild у corpus_manager)."""
        if self._corpus_manager is not None:
            return self._corpus_manager.get_bm25()
        return self._bm25

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        if not text:
            return 0.0

        bm25 = self._get_live_bm25()

        if self._backend == "simple" or bm25 is None:
            raw_score = self._simple_score(text)
        else:
            raw_score = self._bm25_score_with(text, bm25)

        text_lower = text.lower()
        best_cat   = self._best_category_with(text_lower, bm25)

        # ── Антислова ─────────────────────────────────────────────────────────
        neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
        neg_reject_threshold = _neg_reject_threshold(best_cat)

        if neg_hits >= neg_reject_threshold:
            logger.info(
                "BM25: negative keyword reject (hits=%d, threshold=%d, cat=%d/%s)",
                neg_hits, neg_reject_threshold, best_cat,
                _TOPIC_NAMES.get(best_cat, "unknown"),
            )
            return 0.0

        if neg_hits == 1:
            raw_score = max(0.0, raw_score - _NEGATIVE_PENALTY)

        # ── Буст-слова ────────────────────────────────────────────────────────
        boost_hits = sum(1 for kw in _BOOST_KEYWORDS if kw in text_lower)
        if boost_hits > 0:
            raw_score = min(1.0, raw_score + _BOOST_BONUS * min(boost_hits, _BOOST_MAX_HITS))

        # ── Dynamic кластери (Рівень 3) ───────────────────────────────────────
        if self._corpus_manager is not None and bm25 is not None:
            tokens = _tokenize(text_lower)
            if tokens:
                scores = bm25.get_scores(tokens)

                interests_raw  = float(scores[_CAT_USER_INTERESTS])  if len(scores) > _CAT_USER_INTERESTS  else 0.0
                antitopics_raw = float(scores[_CAT_USER_ANTITOPICS]) if len(scores) > _CAT_USER_ANTITOPICS else 0.0

                norm_interests  = min(interests_raw  / self._max_score, 1.0)
                norm_antitopics = min(antitopics_raw / self._max_score, 1.0)

                if norm_interests > 0.05:
                    raw_score = min(1.0, raw_score + 0.25 * norm_interests)
                if norm_antitopics > 0.05:
                    raw_score = max(0.0, raw_score - 0.30 * norm_antitopics)

                logger.debug(
                    "BM25 dynamic: interests=%.3f antitopics=%.3f → %.3f",
                    norm_interests, norm_antitopics, raw_score,
                )

        logger.info(
            "BM25: score=%.3f neg_hits=%d boost_hits=%d best_cat=%d/%s",
            raw_score, neg_hits, boost_hits, best_cat,
            _TOPIC_NAMES.get(best_cat, "unknown"),
        )
        return raw_score

    def _bm25_score_with(self, text: str, bm25) -> float:
        tokens = _tokenize(text)
        if not tokens:
            return 0.0
        scores = bm25.get_scores(tokens)
        # Беремо max тільки по статичних кластерах [0-8]
        static_scores = scores[:len(_TOPIC_CORPUS_RAW)]
        raw = float(np.max(static_scores))
        normalized = min(raw / self._max_score, 1.0)
        logger.debug(
            "BM25: raw_max=%.3f normalized=%.3f best_topic=%d/%s tokens=%d",
            raw, normalized,
            int(np.argmax(static_scores)),
            _TOPIC_NAMES.get(int(np.argmax(static_scores)), "unknown"),
            len(tokens),
        )
        return normalized

    def _best_category_with(self, text_lower: str, bm25) -> int:
        if bm25 is None or self._backend != "rank_bm25":
            return self._best_category_simple(text_lower)
        tokens = _tokenize(text_lower)
        if not tokens:
            return 0
        scores = bm25.get_scores(tokens)
        static_scores = scores[:len(_TOPIC_CORPUS_RAW)]
        return int(np.argmax(static_scores))

    def _best_category_simple(self, text_lower: str) -> int:
        """Fallback: проста перевірка по хітах без BM25."""
        best, best_idx = 0, 0
        for i, keywords in enumerate(_TOPIC_CORPUS_RAW):
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > best:
                best, best_idx = hits, i
        return best_idx

    def _simple_score(self, text: str) -> float:
        """Fallback scoring без rank_bm25."""
        text_lower = text.lower()
        best_hits = 0
        for keywords in _TOPIC_CORPUS_RAW:
            hits = sum(1 for kw in keywords if kw in text_lower)
            best_hits = max(best_hits, hits)
        # Нормалізуємо: припускаємо що 10+ хітів = score 1.0
        return min(best_hits / 10.0, 1.0)